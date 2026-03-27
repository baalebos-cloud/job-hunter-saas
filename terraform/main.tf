# 1. Terraform Settings: Locking in versions for stability
terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional: In a team environment, you would add a 'backend' block here 
  # to store your 'terraform.tfstate' in an S3 bucket.
}

# 2. Provider Configuration: Where we are deploying
provider "aws" {
  region = var.aws_region

  # Default Tags: Every resource created will automatically have these tags
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "Production"
      ManagedBy   = "Terraform"
      Owner       = "Baalebos-DevOps"
    }
  }
}

# 3. Data Sources: Finding existing AWS resources
data "aws_availability_zones" "available" {
  state = "available"
}
