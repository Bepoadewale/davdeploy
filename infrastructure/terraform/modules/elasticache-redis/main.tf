variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "vpc_id" { type = string }
variable "application_security_group_ids" { type = list(string) }
variable "node_type" {
  type    = string
  default = "cache.t4g.micro"
}
variable "auth_token" {
  type      = string
  sensitive = true
  validation {
    condition     = can(regex("^[A-Za-z0-9!&#$^<>-]{16,128}$", var.auth_token))
    error_message = "Redis AUTH token must be 16–128 allowed characters."
  }
}
variable "tags" { type = map(string) }

resource "aws_security_group" "this" {
  name        = "${var.name}-redis"
  description = "Private Redis access from approved application groups only."
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "redis" {
  for_each                     = { for index, security_group_id in var.application_security_group_ids : tostring(index) => security_group_id }
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = each.value
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}

resource "aws_elasticache_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = var.name
  description                = "DavDeploy managed Redis: ${var.name}"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.node_type
  num_cache_clusters         = 1
  port                       = 6379
  auth_token                 = var.auth_token
  auth_token_update_strategy = "SET"
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.this.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"
  automatic_failover_enabled = false
  multi_az_enabled           = false
  tags                       = var.tags
}

output "primary_endpoint" { value = aws_elasticache_replication_group.this.primary_endpoint_address }
