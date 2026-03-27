# 1. The Subnet Group: Tells RDS exactly which "neighborhoods" (AZs) it can live in
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.public1.id, aws_subnet.public2.id]

  tags = {
    Name = "Baalebos-DB-Subnet-Group"
  }
}

# 2. The Security Group: The firewall for your Database
resource "aws_security_group" "rds_sg" {
  name        = "${var.project_name}-rds-sg"
  description = "Allow inbound PostgreSQL traffic"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "PostgreSQL from anywhere"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Allows your local machine to connect
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. The RDS Instance: The Production Database
resource "aws_db_instance" "postgres" {
  identifier        = "${var.project_name}-db-instance"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = "db.t3.micro"
  allocated_storage = 20

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  # --- THE CRITICAL FIXES ---
  # Force it into us-east-1a so it stops trying to find us-east-1f
  availability_zone      = "${var.aws_region}a" 
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  
  publicly_accessible    = true
  skip_final_snapshot    = true

  tags = { Name = "Baalebos-RDS-Production" }
}
