output "customer_discovery_template_url" {
  description = "Public, immutable-by-key CloudFormation template URL. It contains no customer data or secrets."
  value       = "https://${aws_s3_bucket.templates.bucket}.s3.${var.region}.amazonaws.com/${aws_s3_object.current_customer_discovery_role.key}"
}

output "customer_nova_apply_role_template_url" {
  description = "Public, immutable-by-key CloudFormation template URL for the default-off dedicated Nova apply role; it contains no customer data or secrets."
  value       = "https://${aws_s3_bucket.templates.bucket}.s3.${var.region}.amazonaws.com/${aws_s3_object.current_customer_nova_apply_role.key}"
}
