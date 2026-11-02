variable "name" { type = string }
variable "tags" { type = map(string) }

resource "aws_appconfig_application" "this" {
  name = var.name
  tags = var.tags
}

resource "aws_appconfig_environment" "this" {
  application_id = aws_appconfig_application.this.id
  name           = "production"
  tags           = var.tags
}

output "application_id" { value = aws_appconfig_application.this.id }
