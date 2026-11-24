variable "name" { type = string }
variable "ami_id" {
  type = string
  validation {
    condition     = can(regex("^ami-[0-9a-fA-F]{8,17}$", var.ami_id))
    error_message = "ami_id must be a known AMI ID."
  }
}
variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "instance_type" {
  type    = string
  default = "t3.micro"
  validation {
    condition     = var.instance_type == "t3.micro"
    error_message = "This bounded profile supports only t3.micro instances."
  }
}
variable "min_size" {
  type    = number
  default = 1
  validation {
    condition     = var.min_size >= 0 && var.min_size <= 3 && floor(var.min_size) == var.min_size
    error_message = "min_size must be an integer between zero and three."
  }
}
variable "max_size" {
  type    = number
  default = 3
  validation {
    condition     = var.max_size >= 1 && var.max_size <= 3 && floor(var.max_size) == var.max_size
    error_message = "max_size must be an integer between one and three."
  }
}
variable "tags" { type = map(string) }

resource "aws_launch_template" "this" {
  name_prefix            = "${var.name}-"
  image_id               = var.ami_id
  instance_type          = var.instance_type
  vpc_security_group_ids = var.security_group_ids
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
  tag_specifications {
    resource_type = "instance"
    tags          = var.tags
  }
  tags = var.tags
}

resource "aws_autoscaling_group" "this" {
  name                = var.name
  min_size            = var.min_size
  max_size            = var.max_size
  desired_capacity    = var.min_size
  vpc_zone_identifier = var.subnet_ids
  lifecycle {
    precondition {
      condition     = var.min_size <= var.max_size
      error_message = "min_size must not exceed max_size."
    }
  }
  launch_template {
    id      = aws_launch_template.this.id
    version = aws_launch_template.this.latest_version
  }
  dynamic "tag" {
    for_each = merge(var.tags, { Name = var.name })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

output "name" { value = aws_autoscaling_group.this.name }
