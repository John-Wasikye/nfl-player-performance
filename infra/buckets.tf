# Three buckets here, one per lifecycle (see docs/storage-design.md). The tfstate bucket is in
# infra/bootstrap. Every bucket: Block Public Access, SSE-S3, TLS only, versioned.

locals {
  buckets = {
    raw     = "${var.bucket_prefix}-raw"
    records = "${var.bucket_prefix}-records"
    site    = "${var.bucket_prefix}-site"
  }
}

resource "aws_s3_bucket" "raw" {
  bucket = local.buckets.raw
}

# Object Lock can only be switched on when the bucket is created, so it is set here.
resource "aws_s3_bucket" "records" {
  bucket              = local.buckets.records
  object_lock_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "site" {
  bucket = local.buckets.site
}

locals {
  bucket_ids = {
    raw     = aws_s3_bucket.raw.id
    records = aws_s3_bucket.records.id
    site    = aws_s3_bucket.site.id
  }
  bucket_arns = {
    raw     = aws_s3_bucket.raw.arn
    records = aws_s3_bucket.records.arn
    site    = aws_s3_bucket.site.arn
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = local.bucket_ids
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "all" {
  for_each = local.bucket_ids
  bucket   = each.value
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = local.bucket_ids
  bucket   = each.value
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "tls_only" {
  for_each = local.bucket_ids

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [local.bucket_arns[each.key], "${local.bucket_arns[each.key]}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# The site bucket's CloudFront OAC statement is added in the CloudFront step and will extend this policy.
resource "aws_s3_bucket_policy" "tls_only" {
  for_each = local.bucket_ids
  bucket   = each.value
  policy   = data.aws_iam_policy_document.tls_only[each.key].json

  depends_on = [aws_s3_bucket_public_access_block.all]
}

# Governance mode: overriding needs s3:BypassGovernanceRetention plus an explicit header, and shows in
# CloudTrail. Tamper-evident rather than tamper-proof, by design.
resource "aws_s3_bucket_object_lock_configuration" "records" {
  bucket = aws_s3_bucket.records.id

  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = var.records_retention_days
    }
  }

  depends_on = [aws_s3_bucket_versioning.all]
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.raw_noncurrent_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.all]
}

resource "aws_s3_bucket_lifecycle_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.site_noncurrent_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.all]
}

# Records: no expiry rule, only a cleanup for stray multipart uploads.
resource "aws_s3_bucket_lifecycle_configuration" "records" {
  bucket = aws_s3_bucket.records.id

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.all]
}
