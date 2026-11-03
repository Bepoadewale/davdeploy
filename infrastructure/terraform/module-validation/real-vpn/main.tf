data "aws_availability_zones" "available" { state = "available" }

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

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

resource "aws_security_group" "peer" {
  name_prefix = "${local.name}-peer-"
  vpc_id      = aws_vpc.peer.id
  ingress {
    from_port   = 500
    to_port     = 500
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 4500
    to_port     = 4500
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = ["10.240.0.0/16"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group" "workload" {
  name_prefix = "${local.name}-workload-"
  vpc_id      = aws_vpc.workload.id
  ingress {
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = ["10.250.0.0/16"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_iam_role" "peer_ssm" {
  name = "${local.name}-peer-ssm"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "peer_ssm" {
  role       = aws_iam_role.peer_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "peer_vpn_sample" {
  name = "read-own-vpn-sample"
  role = aws_iam_role.peer_ssm.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ec2:GetVpnConnectionDeviceSampleConfiguration"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_instance_profile" "peer_ssm" {
  name = "${local.name}-peer-ssm"
  role = aws_iam_role.peer_ssm.name
}

resource "aws_instance" "peer" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.peer.id
  vpc_security_group_ids = [aws_security_group.peer.id]
  source_dest_check      = false
  user_data              = <<-EOT
    #!/bin/bash
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y strongswan awscli
    systemctl enable --now strongswan-starter
  EOT
  tags                   = merge(local.tags, { Name = "${local.name}-peer" })
}

// The pinned AWS provider does not expose an instance-profile association
// resource. Keep this bounded, disposable association in Terraform so the
// certification uses Session Manager rather than a public SSH key.
resource "terraform_data" "peer_ssm_association" {
  triggers_replace = [
    aws_instance.peer.id,
    aws_iam_instance_profile.peer_ssm.name,
  ]

  provisioner "local-exec" {
    command = "aws ec2 associate-iam-instance-profile --region ${var.region} --instance-id ${aws_instance.peer.id} --iam-instance-profile Arn=${aws_iam_instance_profile.peer_ssm.arn}"
  }
}

resource "aws_instance" "workload" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.workload.id
  vpc_security_group_ids = [aws_security_group.workload.id]
  tags                   = merge(local.tags, { Name = "${local.name}-workload" })
}

module "vpn" {
  source                   = "../../modules/site-to-site-vpn"
  name                     = local.name
  vpc_id                   = aws_vpc.workload.id
  customer_gateway_ip      = aws_instance.peer.public_ip
  static_routes_only       = true
  remote_ipv4_network_cidr = "10.250.0.0/16"
  tags                     = local.tags
}

resource "aws_vpn_gateway_route_propagation" "workload" {
  vpn_gateway_id = module.vpn.vpn_gateway_id
  route_table_id = aws_vpc.workload.default_route_table_id
}

output "peer_public_ip" { value = aws_instance.peer.public_ip }
output "peer_instance_id" { value = aws_instance.peer.id }
output "workload_private_ip" { value = aws_instance.workload.private_ip }
output "vpn_connection_id" { value = module.vpn.vpn_connection_id }
