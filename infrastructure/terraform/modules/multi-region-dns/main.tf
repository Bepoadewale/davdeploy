variable "zone_id" { type = string }
variable "name" { type = string }
variable "primary_endpoint" { type = string }
variable "secondary_endpoint" { type = string }
variable "health_check_type" {
  type    = string
  default = "HTTPS"
  validation {
    condition     = contains(["HTTP", "HTTPS"], var.health_check_type)
    error_message = "health_check_type must be HTTP or HTTPS."
  }
}
variable "health_check_port" {
  type    = number
  default = 443
}
variable "health_check_path" {
  type    = string
  default = "/health"
}
variable "tags" { type = map(string) }

resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_endpoint
  port              = var.health_check_port
  type              = var.health_check_type
  resource_path     = var.health_check_path
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
