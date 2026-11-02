variable "name" { type = string }
variable "shard_count" {
  type    = number
  default = 1
}
variable "tags" { type = map(string) }

resource "aws_kinesis_stream" "this" {
  name             = var.name
  shard_count      = var.shard_count
  retention_period = 24
  encryption_type  = "KMS"
  kms_key_id       = "alias/aws/kinesis"
  tags             = var.tags
}

output "arn" { value = aws_kinesis_stream.this.arn }
