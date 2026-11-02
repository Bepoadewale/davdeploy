variable "name" { type = string }
variable "tags" { type = map(string) }

resource "aws_kms_key" "this" {
  description             = "DavDeploy managed key: ${var.name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = var.tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.this.key_id
}

output "key_arn" { value = aws_kms_key.this.arn }
