variable "aws_region" {
  description = "The AWS region to deploy the JobHunter infrastructure"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "The prefix used for naming all Baalebos resources"
  type        = string
  default     = "jobhunter"
}

variable "instance_type" {
  description = "The EC2 instance size for the API workers"
  type        = string
  default     = "t3.micro"
}

variable "db_username" {
  description = "The master username for the PostgreSQL database"
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "The master password for the PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "The initial database name to create"
  type        = string
  default     = "jobhunter"
}
