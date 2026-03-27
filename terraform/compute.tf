# 1. EC2 Security Group (The "Server Firewall")
resource "aws_security_group" "web_sg" {
  name        = "${var.project_name}-web-sg"
  description = "Allow traffic to Baalebos API"
  vpc_id      = aws_vpc.main.id

  # Allow the Load Balancer to talk to FastAPI on Port 8000
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  # Allow SSH for you to debug the Ubuntu server
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # In prod, change to your specific IP
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 2. Launch Template (The "Server Blueprint")
resource "aws_launch_template" "api" {
  name_prefix   = "jobhunter-api-"
  image_id      = "ami-0c7217cdde317cfec" # Ubuntu 22.04
  instance_type = var.instance_type

  vpc_security_group_ids = [aws_security_group.web_sg.id]

  user_data = base64encode(<<EOF
#!/bin/bash
apt-get update -y
apt-get install -y docker.io
systemctl start docker
systemctl enable docker
# Momentum: Pulling the latest production engine
docker pull baalebos/jobhunter-api:latest
docker run -d -p 8000:8000 \
  -e DATABASE_URL=${aws_db_instance.postgres.endpoint} \
  -e REDIS_URL=redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0 \
  baalebos/jobhunter-api:latest
EOF
  )
}

# 3. Auto Scaling Group (The "Scale Engine")
resource "aws_autoscaling_group" "api" {
  desired_capacity    = 2
  min_size            = 2
  max_size            = 4
  vpc_zone_identifier = [aws_subnet.public1.id, aws_subnet.public2.id]

  # CRITICAL: Connects the ASG to the Load Balancer
  target_group_arns = [aws_lb_target_group.api.arn]

  launch_template {
    id      = aws_launch_template.api.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "Baalebos-API-Worker"
    propagate_at_launch = true
  }
}
