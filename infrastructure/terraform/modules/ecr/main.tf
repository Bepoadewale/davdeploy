variable "name" { type = string }
variable "tags" { type = map(string) }

resource "aws_ecr_repository" "this" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
  tags = var.tags
}
output "repository_url" { value = aws_ecr_repository.this.repository_url }
