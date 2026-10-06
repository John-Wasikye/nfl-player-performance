# CloudFront in front of the private site bucket. The bucket stays closed to the public: the only reader is
# this distribution, through Origin Access Control. The custom domain and certificate arrive in step 19; until
# then the site is reachable on the distribution's own *.cloudfront.net name.
#
# Pay-as-you-go pricing, not a flat-rate plan: the AWS provider cannot select one, and the always-free tier
# (1 TB and 10 million requests a month) covers this site many times over. It also avoids the web ACL that
# the free flat-rate plan makes mandatory.

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "nfl-site"
  description                       = "Lets CloudFront read the private site bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Pages are exported with trailingSlash, so /about/ lives at about/index.html. S3 does not do that mapping.
resource "aws_cloudfront_function" "rewrite" {
  name    = "nfl-site-rewrite"
  runtime = "cloudfront-js-2.0"
  publish = true
  comment = "Serve directory index pages; send extensionless paths to the trailing-slash form"
  code    = <<-JS
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      if (uri.endsWith('/')) {
        request.uri = uri + 'index.html';
        return request;
      }
      var last = uri.substring(uri.lastIndexOf('/') + 1);
      if (last.indexOf('.') === -1) {
        return {
          statusCode: 301,
          statusDescription: 'Moved Permanently',
          headers: { location: { value: uri + '/' } }
        };
      }
      return request;
    }
  JS
}

# Page code: hashed assets carry their own long Cache-Control; everything else is capped at a day.
resource "aws_cloudfront_cache_policy" "site" {
  name        = "nfl-site-pages"
  default_ttl = 300
  min_ttl     = 0
  max_ttl     = 31536000

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

# The published JSON changes once a day. A short cap means a new run shows up within minutes without an
# invalidation, whatever Cache-Control the pipeline wrote.
resource "aws_cloudfront_cache_policy" "data" {
  name        = "nfl-site-data"
  default_ttl = 120
  min_ttl     = 0
  max_ttl     = 300

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name = "nfl-site-security"

  security_headers_config {
    content_security_policy {
      override = true
      # Next's static export writes inline scripts and styles, so 'unsafe-inline' is needed for both.
      content_security_policy = join("; ", [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
      ])
    }
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      override                   = true
    }
  }

  custom_headers_config {
    items {
      header   = "Permissions-Policy"
      value    = "camera=(), microphone=(), geolocation=(), payment=()"
      override = true
    }
  }
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  comment             = "NFL Player Performance site"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  aliases             = var.attach_domain ? [var.site_domain] : []

  origin {
    origin_id                = "site-bucket"
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id           = "site-bucket"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = aws_cloudfront_cache_policy.site.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.rewrite.arn
    }
  }

  ordered_cache_behavior {
    path_pattern               = "data/v1/*"
    target_origin_id           = "site-bucket"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = aws_cloudfront_cache_policy.data.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
  }

  # With the bucket private, a missing key comes back as 403 or 404. Both show the site's own not-found page,
  # and both keep a real 404 status so a broken link is not reported as a success.
  custom_error_response {
    error_code            = 403
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 10
  }
  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # The distribution's own *.cloudfront.net certificate until the domain is attached (domain.tf).
  viewer_certificate {
    cloudfront_default_certificate = var.attach_domain ? null : true
    acm_certificate_arn            = var.attach_domain ? aws_acm_certificate_validation.site[0].certificate_arn : null
    ssl_support_method             = var.attach_domain ? "sni-only" : null
    minimum_protocol_version       = var.attach_domain ? "TLSv1.2_2021" : null
  }
}

# The bucket's only reader. Added to the TLS-only statement in buckets.tf.
data "aws_iam_policy_document" "cloudfront_read" {
  statement {
    sid       = "AllowCloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }

  # Without list permission S3 answers 403 for a missing key; with it, 404.
  statement {
    sid       = "AllowCloudFrontList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.site.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

output "site_url" {
  value = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "site_distribution_id" {
  value = aws_cloudfront_distribution.site.id
}
