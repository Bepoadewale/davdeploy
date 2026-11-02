variable "name" { type = string }
variable "execution_role_arn" { type = string }
variable "image_uri" { type = string }
variable "instance_type" {
  type    = string
  default = "ml.m5.large"
}
variable "tags" { type = map(string) }

resource "aws_sagemaker_model" "this" {
  name               = var.name
  execution_role_arn = var.execution_role_arn
  primary_container { image = var.image_uri }
  tags = var.tags
}

resource "aws_sagemaker_endpoint_configuration" "this" {
  name = var.name
  production_variants {
    variant_name           = "primary"
    model_name             = aws_sagemaker_model.this.name
    initial_instance_count = 1
    instance_type          = var.instance_type
  }
  tags = var.tags
}

resource "aws_sagemaker_endpoint" "this" {
  name                 = var.name
  endpoint_config_name = aws_sagemaker_endpoint_configuration.this.name
  tags                 = var.tags
}

output "endpoint_name" { value = aws_sagemaker_endpoint.this.name }
