# Private, KMS-encrypted bucket for resume PDFs (RESUME_S3_BUCKET).
resource "aws_kms_key" "resumes" {
  description         = "${var.project_name} resume PDFs"
  enable_key_rotation = true
}

resource "aws_s3_bucket" "resumes" {
  bucket = "${var.project_name}-resumes-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "resumes" {
  bucket                  = aws_s3_bucket.resumes.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "resumes" {
  bucket = aws_s3_bucket.resumes.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "resumes" {
  bucket = aws_s3_bucket.resumes.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.resumes.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "resumes" {
  bucket = aws_s3_bucket.resumes.id
  versioning_configuration { status = "Enabled" }
}

# Retention: erased/replaced objects (non-current versions) are purged after
# 30 days; abandoned uploads after 1 day. Application-level retention of live
# resumes is handled by the privacy retention job.
resource "aws_s3_bucket_lifecycle_configuration" "resumes" {
  bucket = aws_s3_bucket.resumes.id
  rule {
    id     = "purge-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}

resource "aws_s3_bucket_policy" "resumes_tls_only" {
  bucket = aws_s3_bucket.resumes.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.resumes.arn, "${aws_s3_bucket.resumes.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_iam_role_policy" "api_resumes" {
  name = "${var.project_name}-api-resumes"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"], Resource = "${aws_s3_bucket.resumes.arn}/resumes/*" },
      { Effect = "Allow", Action = ["kms:GenerateDataKey", "kms:Decrypt"], Resource = aws_kms_key.resumes.arn }
    ]
  })
}

output "resume_bucket" { value = aws_s3_bucket.resumes.bucket }
output "resume_kms_key_arn" { value = aws_kms_key.resumes.arn }
