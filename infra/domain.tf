# The site's own address. DNS lives at Cloudflare, so two records are added there by hand:
#   1. a validation CNAME, so AWS can confirm the domain is yours before issuing the certificate;
#   2. a CNAME from the site name to the CloudFront distribution.
# Cloudflare must serve both as "DNS only" (grey cloud), not proxied.
#
# Two phases, because the certificate cannot be issued until record 1 exists:
#   attach_domain = false  request the certificate and print record 1
#   attach_domain = true   wait for it to be issued, then serve the site under the domain (now the default)
# CloudFront only accepts certificates from us-east-1, which is this configuration's region.

variable "site_domain" {
  type    = string
  default = "nflstats.johnwasikye.com"
}

variable "attach_domain" {
  description = "True once the validation record is in DNS and the certificate has been issued."
  type        = bool
  default     = true
}

resource "aws_acm_certificate" "site" {
  domain_name       = var.site_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "site" {
  count                   = var.attach_domain ? 1 : 0
  certificate_arn         = aws_acm_certificate.site.arn
  validation_record_fqdns = [for option in aws_acm_certificate.site.domain_validation_options : option.resource_record_name]

  timeouts {
    create = "10m"
  }
}

output "dns_record_1_certificate_validation" {
  description = "Add this CNAME at Cloudflare (DNS only). Name is the full name; Cloudflare accepts it with or without the zone suffix."
  value = {
    for option in aws_acm_certificate.site.domain_validation_options : option.domain_name => {
      type   = option.resource_record_type
      name   = option.resource_record_name
      target = option.resource_record_value
    }
  }
}

output "dns_record_2_site" {
  description = "Add this CNAME at Cloudflare (DNS only) once the domain is attached."
  value = {
    type   = "CNAME"
    name   = var.site_domain
    target = aws_cloudfront_distribution.site.domain_name
  }
}
