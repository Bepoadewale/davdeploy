output "table_name" {
  value = local.table_name
}

output "table_arn" {
  value = module.dynamodb_table.arn
}
