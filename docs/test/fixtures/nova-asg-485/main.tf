variable "test_id" {
  type    = string
  default = "nova-asg-485"
}

variable "min_size" {
  type    = number
  default = 1
}

locals {
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-nova-asg-lifecycle-test"
    TestId    = var.test_id
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_vpc" "test" {
  cidr_block           = "10.248.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "davdeploy-${var.test_id}" })
}

resource "aws_subnet" "isolated" {
  count                   = 2
  vpc_id                  = aws_vpc.test.id
  cidr_block              = "10.248.${count.index}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
  tags = merge(local.tags, {
    Name = "davdeploy-${var.test_id}-${count.index}"
  })
}

resource "aws_route_table" "isolated" {
  vpc_id = aws_vpc.test.id
  tags   = local.tags
}

resource "aws_route_table_association" "isolated" {
  count          = length(aws_subnet.isolated)
  subnet_id      = aws_subnet.isolated[count.index].id
  route_table_id = aws_route_table.isolated.id
}

resource "aws_security_group" "instance" {
  name_prefix = "davdeploy-${var.test_id}-"
  description = "Isolated Auto Scaling lifecycle test; no ingress or egress rules."
  vpc_id      = aws_vpc.test.id
  ingress     = []
  egress      = []
  tags        = local.tags
}

module "ec2_autoscaling" {
  source             = "../../../../infrastructure/terraform/modules/ec2-autoscaling"
  name               = "davdeploy-${var.test_id}"
  ami_id             = data.aws_ssm_parameter.al2023.value
  subnet_ids         = aws_subnet.isolated[*].id
  security_group_ids = [aws_security_group.instance.id]
  min_size           = var.min_size
  max_size           = 2
  tags               = local.tags
}
