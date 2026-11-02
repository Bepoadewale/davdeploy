variable "name" { type = string }
variable "hash_key" { type = string }
variable "hash_key_type" {
  type    = string
  default = "S"
}
variable "tags" { type = map(string) }

resource "aws_dynamodb_table" "this" {
  name         = var.name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = var.hash_key

  attribute {
    name = var.hash_key
    type = var.hash_key_type
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = var.tags
}

output "arn" { value = aws_dynamodb_table.this.arn }
