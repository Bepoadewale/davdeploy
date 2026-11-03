data "aws_availability_zones" "available" { state = "available" }

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

locals {
  name = "davdeploy-${var.test_id}"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

resource "aws_vpc" "workload" {
  cidr_block           = "10.240.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.tags, { Name = "${local.name}-workload" })
}

resource "aws_vpc" "peer" {
  cidr_block           = "10.250.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.tags, { Name = "${local.name}-peer" })
}

resource "aws_internet_gateway" "peer" {
  vpc_id = aws_vpc.peer.id
  tags   = local.tags
}

resource "aws_subnet" "workload" {
  vpc_id            = aws_vpc.workload.id
  cidr_block        = "10.240.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
  tags              = local.tags
}

resource "aws_subnet" "peer" {
  vpc_id                  = aws_vpc.peer.id
  cidr_block              = "10.250.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = local.tags
}

resource "aws_route_table" "peer" {
  vpc_id = aws_vpc.peer.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.peer.id
  }
  tags = local.tags
}

resource "aws_route_table_association" "peer" {
  subnet_id      = aws_subnet.peer.id
  route_table_id = aws_route_table.peer.id
}
