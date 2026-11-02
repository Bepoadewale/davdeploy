variable "test_id" { type = string }

locals {
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "application" {
  name_prefix = "davdeploy-${var.test_id}-"
  vpc_id      = data.aws_vpc.default.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

module "ec2_autoscaling" {
  source             = "../../modules/ec2-autoscaling"
  name               = "davdeploy-${var.test_id}"
  ami_id             = data.aws_ssm_parameter.al2023.value
  subnet_ids         = slice(data.aws_subnets.default.ids, 0, 2)
  security_group_ids = [aws_security_group.application.id]
  min_size           = 0
  max_size           = 1
  tags               = local.tags
}

output "autoscaling_group" { value = module.ec2_autoscaling.name }
