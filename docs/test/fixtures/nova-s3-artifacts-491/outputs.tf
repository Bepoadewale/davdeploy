output "bucket_name" {
  value = module.artifacts.bucket_name
}

output "test_id" {
  value = "nova-s3-artifacts-491-${var.run_id}"
}
