variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "vpc_id" { type = string }
variable "application_security_group_ids" {
  type        = list(string)
  description = "Only explicitly approved application security groups may reach PostgreSQL."
}
variable "database_name" {
  type    = string
  default = "application"
}
variable "deletion_protection" {
  type    = bool
  default = true
}
variable "skip_final_snapshot" {
  type    = bool
  default = false
}
variable "tags" { type = map(string) }

resource "aws_security_group" "database" {
  name        = "${var.name}-database"
  description = "Private Aurora PostgreSQL access from approved application groups only."
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  for_each                     = toset(var.application_security_group_ids)
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-aurora"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_rds_cluster" "this" {
  cluster_identifier          = var.name
  engine                      = "aurora-postgresql"
  engine_mode                 = "provisioned"
  database_name               = var.database_name
  master_username             = "davdeploy"
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.this.name
  vpc_security_group_ids      = [aws_security_group.database.id]
  storage_encrypted           = true
  backup_retention_period     = 7
  deletion_protection         = var.deletion_protection
  skip_final_snapshot         = var.skip_final_snapshot
  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 2
  }
  tags = var.tags
}

resource "aws_rds_cluster_instance" "writer" {
  identifier         = "${var.name}-writer"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
  tags               = var.tags
}

output "cluster_arn" { value = aws_rds_cluster.this.arn }
