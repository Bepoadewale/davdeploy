variable "name" { type = string }
variable "tags" { type = map(string) }

resource "aws_route53_zone" "this" {
  name          = var.name
  force_destroy = false
  tags          = var.tags
}

output "zone_id" { value = aws_route53_zone.this.zone_id }
output "name_servers" { value = aws_route53_zone.this.name_servers }
