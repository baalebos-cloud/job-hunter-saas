# 1. Redis Subnet Group (Plugs Redis into your Public Subnets)
resource "aws_elasticache_subnet_group" "redis_subnets" {
  name       = "${var.project_name}-redis-subnet-group"
  subnet_ids = [aws_subnet.public1.id, aws_subnet.public2.id]
}

# 2. Redis Security Group (The Firewall)
resource "aws_security_group" "redis_sg" {
  name        = "${var.project_name}-redis-sg"
  description = "Allow Redis traffic from EC2"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Redis from EC2"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    # Only allow your EC2 instance's Security Group to connect
    security_groups = [aws_security_group.web_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. The ElastiCache Cluster
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis_subnets.name
  security_group_ids = [aws_security_group.redis_sg.id]

  tags = { Name = "Baalebos-Redis-Production" }
}
