variable "name" { type = string }
variable "cidr" { type = string }
variable "azs" { type = list(string) }
variable "tags" { type = map(string) }

resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(var.tags, { Name = var.name })
}

resource "aws_subnet" "private" {
  for_each                = { for index, az in var.azs : index => az }
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr, 4, each.key)
  availability_zone       = each.value
  map_public_ip_on_launch = false
  tags = merge(var.tags, {
    Name                              = "${var.name}-private-${each.key}",
    "kubernetes.io/role/internal-elb" = "1",
  })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-igw" })
}

resource "aws_subnet" "public" {
  for_each                = { for index, az in var.azs : index => az }
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr, 4, each.key + 8)
  availability_zone       = each.value
  map_public_ip_on_launch = false
  tags = merge(var.tags, {
    Name                     = "${var.name}-public-${each.key}",
    "kubernetes.io/role/elb" = "1",
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(var.tags, { Name = "${var.name}-public" })
}
resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}
resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name}-nat" })
}
resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = values(aws_subnet.public)[0].id
  depends_on    = [aws_internet_gateway.this]
  tags          = merge(var.tags, { Name = "${var.name}-nat" })
}
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }
  tags = merge(var.tags, { Name = "${var.name}-private" })
}
resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

output "vpc_id" { value = aws_vpc.this.id }
output "nat_gateway_id" { value = aws_nat_gateway.this.id }
output "nat_public_ipv4" { value = aws_eip.nat.public_ip }
output "private_subnet_ids" { value = values(aws_subnet.private)[*].id }
output "public_subnet_ids" { value = values(aws_subnet.public)[*].id }
output "private_route_table_id" { value = aws_route_table.private.id }
