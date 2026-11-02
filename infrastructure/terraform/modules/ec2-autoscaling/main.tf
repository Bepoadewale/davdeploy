variable "name" { type = string }
variable "ami_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "instance_type" {
  type    = string
  default = "t3.micro"
}
variable "min_size" {
  type    = number
  default = 1
}
variable "max_size" {
  type    = number
  default = 3
}
variable "tags" { type = map(string) }

resource "aws_launch_template" "this" {
  name_prefix            = "${var.name}-"
  image_id               = var.ami_id
  instance_type          = var.instance_type
  vpc_security_group_ids = var.security_group_ids
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
  launch_template {
    id      = aws_launch_template.this.id
    version = "$Latest"
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
