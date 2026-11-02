variable "zone_id" { type = string }
variable "name" { type = string }
variable "primary_endpoint" { type = string }
variable "secondary_endpoint" { type = string }
variable "tags" { type = map(string) }

resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_endpoint
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30
  tags              = merge(var.tags, { Name = "${var.name}-primary" })
}

resource "aws_route53_record" "primary" {
  zone_id         = var.zone_id
  name            = var.name
  type            = "CNAME"
  ttl             = 60
  records         = [var.primary_endpoint]
  health_check_id = aws_route53_health_check.primary.id
  set_identifier  = "primary"
  failover_routing_policy { type = "PRIMARY" }
}

resource "aws_route53_record" "secondary" {
  zone_id        = var.zone_id
  name           = var.name
  type           = "CNAME"
  ttl            = 60
  records        = [var.secondary_endpoint]
  set_identifier = "secondary"
  failover_routing_policy { type = "SECONDARY" }
}
