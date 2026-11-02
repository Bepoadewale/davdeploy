variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "vpc_id" { type = string }
variable "application_security_group_ids" { type = list(string) }
variable "instance_type" {
  type    = string
  default = "t3.small.search"
}
variable "tags" { type = map(string) }

resource "aws_security_group" "this" {
  name        = "${var.name}-search"
  description = "Private OpenSearch access from approved application groups only."
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  for_each                     = { for index, security_group_id in var.application_security_group_ids : tostring(index) => security_group_id }
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = each.value
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
}

resource "aws_opensearch_domain" "this" {
  domain_name    = var.name
  engine_version = "OpenSearch_2.11"

  cluster_config {
    instance_type          = var.instance_type
    instance_count         = 1
    zone_awareness_enabled = false
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = 10
  }

  vpc_options {
    subnet_ids         = [var.subnet_ids[0]]
    security_group_ids = [aws_security_group.this.id]
  }

  encrypt_at_rest { enabled = true }
  node_to_node_encryption { enabled = true }
  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }
  tags = var.tags
}

output "endpoint" { value = aws_opensearch_domain.this.endpoint }
