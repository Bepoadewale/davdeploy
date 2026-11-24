output "autoscaling_group_name" {
  value = module.ec2_autoscaling.name
}

output "test_vpc_id" {
  value = aws_vpc.test.id
}
