variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "vpc_id" { type = string }
variable "application_security_group_ids" { type = list(string) }
variable "tags" { type = map(string) }

resource "aws_security_group" "this" {
  name        = "${var.name}-efs"
  description = "Private EFS access from approved application groups only."
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "nfs" {
  for_each                     = { for index, security_group_id in var.application_security_group_ids : tostring(index) => security_group_id }
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = each.value
  from_port                    = 2049
  to_port                      = 2049
  ip_protocol                  = "tcp"
}

resource "aws_efs_file_system" "this" {
  encrypted = true
  tags      = merge(var.tags, { Name = var.name })
}

resource "aws_efs_mount_target" "this" {
  for_each        = toset(var.subnet_ids)
  file_system_id  = aws_efs_file_system.this.id
  subnet_id       = each.value
  security_groups = [aws_security_group.this.id]
}

output "file_system_id" { value = aws_efs_file_system.this.id }
