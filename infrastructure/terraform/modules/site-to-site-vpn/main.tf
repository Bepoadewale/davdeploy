variable "name" { type = string }
variable "vpc_id" { type = string }
variable "customer_gateway_ip" { type = string }
variable "customer_gateway_bgp_asn" {
  type    = number
  default = 65000
}
variable "static_routes_only" {
  type    = bool
  default = false
}
variable "tags" { type = map(string) }

resource "aws_customer_gateway" "this" {
  bgp_asn    = var.customer_gateway_bgp_asn
  ip_address = var.customer_gateway_ip
  type       = "ipsec.1"
  tags       = merge(var.tags, { Name = "${var.name}-customer-gateway" })
}

resource "aws_vpn_gateway" "this" {
  vpc_id = var.vpc_id
  tags   = merge(var.tags, { Name = "${var.name}-vpn-gateway" })
}

resource "aws_vpn_connection" "this" {
  vpn_gateway_id      = aws_vpn_gateway.this.id
  customer_gateway_id = aws_customer_gateway.this.id
  type                = "ipsec.1"
  static_routes_only  = var.static_routes_only
  tags                = var.tags
}

output "vpn_connection_id" { value = aws_vpn_connection.this.id }
