terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.40" }
  }
  # Remote state: encrypted S3 + DynamoDB locking (created by ./bootstrap).
  # Partial configuration so no account details are committed:
  #   terraform init -backend-config=backend.hcl -migrate-state
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" { default = "us-east-1" }
