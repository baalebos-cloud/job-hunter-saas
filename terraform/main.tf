# --- VARIABLES ---
variable "project_name"     { default = "jobhunter" }
variable "db_username"      { default = "postgres" }
variable "db_password"      { default = "SuperDevOps_Cloud0544!?" }
variable "db_name"          { default = "jobhunter" }

# --- DATA SOURCE FOR LATEST AMI ---
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023*-kernel-6.1-x86_64"]
  }
}

# --- NETWORK LAYER ---
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
}

# Public subnets for EC2/ALB
resource "aws_subnet" "public1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true
}
resource "aws_subnet" "public2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = true
}

# Private subnets for RDS
resource "aws_subnet" "private1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "us-east-1a"
}
resource "aws_subnet" "private2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.4.0/24"
  availability_zone = "us-east-1b"
}

# Route tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
}
resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.public1.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "b" {
  subnet_id      = aws_subnet.public2.id
  route_table_id = aws_route_table.public.id
}

# --- SECURITY GROUPS ---
resource "aws_security_group" "alb_sg" {
  name   = "${var.project_name}-alb-sg-v3"
  vpc_id = aws_vpc.main.id

  # Allow inbound HTTP traffic from anywhere
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow outbound traffic to anywhere
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "web_sg" {
  name   = "${var.project_name}-web-sg-v3"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port       = 5000
    to_port         = 5000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds_sg" {
  name   = "${var.project_name}-rds-sg-v3"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    # Allow the entire VPC internal range (10.0.0.0/16) 
    # to talk to the database
    cidr_blocks = ["10.0.1.0/24", "10.0.2.0/24"] 
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- DATABASE LAYER (RDS) ---
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.private1.id, aws_subnet.private2.id]
}

resource "aws_db_instance" "postgres" {
  identifier             = "jobhunter-db-instance"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  publicly_accessible    = false   # safer in private subnets
  skip_final_snapshot    = true
}

# --- COMPUTE LAYER ---
resource "aws_launch_template" "api" {
  name_prefix   = "${var.project_name}-api-"
  image_id      = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.micro"
  key_name      = "devops-key"

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [aws_security_group.web_sg.id]
  }

  user_data = base64encode(<<-EOF
              #!/bin/bash
              dnf update -y
              dnf install -y docker awscli
              systemctl start docker
              systemctl enable docker
              usermod -aG docker ec2-user

              sleep 30

              docker run -d --name redis -p 6379:6379 redis:alpine

              # Fetch secrets from SSM Parameter Store
              MAIL_PASSWORD=$(aws ssm get-parameter --name "/jobhunter/mail_password" --with-decryption --query "Parameter.Value" --output text)
              OPENAI_API_KEY=$(aws ssm get-parameter --name "/jobhunter/openai_api_key" --with-decryption --query "Parameter.Value" --output text)

              docker run -d --name jobhunter-api -p 5000:8000 \
                --restart always \
                --link redis:redis \
                -e DATABASE_URL="postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:5432/${var.db_name}" \
                -e REDIS_URL="redis://redis:6379/0" \
                -e SECRET_KEY="BAALEBOS_PROD_SECRET_2026" \
                -e OPENAI_API_KEY="$OPENAI_API_KEY" \
                -e MAIL_USERNAME="alldatatechsolu@gmail.com" \
                -e MAIL_PASSWORD="$MAIL_PASSWORD" \
                -e MAIL_SERVER="smtp.gmail.com" \
                -e MAIL_PORT="587" \
                -e ENVIRONMENT="production" \
                baalebos/jobhunter-api:latest
              EOF
  )
}

resource "aws_autoscaling_group" "api" {
  name                = "${var.project_name}-asg-v3"
  desired_capacity    = 2
  max_size            = 4
  min_size            = 2
  vpc_zone_identifier = [aws_subnet.public1.id, aws_subnet.public2.id]

  target_group_arns   = [aws_lb_target_group.app_tg.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  launch_template {
    id      = aws_launch_template.api.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "jobhunter-asg-instance"
  propagate_at_launch = true
  }
}

# --- LOAD BALANCER ---
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb-v3"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [aws_subnet.public1.id, aws_subnet.public2.id]
}

resource "aws_lb_target_group" "app_tg" {
  name     = "${var.project_name}-api-tg-v3"
  port     = 5000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    path                = "/health"
    port                = "5000"
    protocol            = "HTTP"
    timeout             = 10
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 2
    matcher             = "200"
  }
}

resource "aws_lb_listener" "front_end" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app_tg.arn
  }
}

output "alb_url" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}
