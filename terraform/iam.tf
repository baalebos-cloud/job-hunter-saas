# Instance role: read only this app's secrets (SSM path + the RDS-managed secret).
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_role" "api" {
  name = "${var.project_name}-api"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "api_secrets" {
  name = "${var.project_name}-api-secrets"
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_parameter_prefix}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_db_instance.postgres.master_user_secret[0].secret_arn
      },
      {
        # Decrypt SecureString parameters / the RDS secret via their KMS keys.
        Effect    = "Allow"
        Action    = ["kms:Decrypt"]
        Resource  = "*"
        Condition = { StringEquals = { "kms:ViaService" = ["ssm.${data.aws_region.current.name}.amazonaws.com", "secretsmanager.${data.aws_region.current.name}.amazonaws.com"] } }
      }
    ]
  })
}

resource "aws_iam_instance_profile" "api" {
  name = "${var.project_name}-api"
  role = aws_iam_role.api.name
}

output "db_master_secret_arn" {
  description = "Secrets Manager ARN of the RDS-managed master credential"
  value       = aws_db_instance.postgres.master_user_secret[0].secret_arn
}
