variable "name" { type = string }
variable "tags" { type = map(string) }

resource "aws_kms_key" "this" {
  description              = "DavDeploy managed key: ${var.name}"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  key_usage                = "ENCRYPT_DECRYPT"
  deletion_window_in_days  = 30
  enable_key_rotation      = true
  multi_region             = false
  tags                     = var.tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.this.key_id
}

output "key_arn" { value = aws_kms_key.this.arn }
