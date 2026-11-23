variable "name" { type = string }
variable "shard_count" {
  type    = number
  default = 1
  validation {
    condition     = var.shard_count == 1
    error_message = "This bounded Kinesis module supports exactly one provisioned shard."
  }
}
variable "tags" { type = map(string) }

resource "aws_kinesis_stream" "this" {
  name             = var.name
  shard_count      = var.shard_count
  retention_period = 24
  encryption_type  = "KMS"
  kms_key_id       = "alias/aws/kinesis"
  stream_mode_details {
    stream_mode = "PROVISIONED"
  }
  tags = var.tags
}

output "arn" { value = aws_kinesis_stream.this.arn }
