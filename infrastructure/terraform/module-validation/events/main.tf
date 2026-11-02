locals {
  name = "davdeploy-${var.test_id}"
  tags = { ManagedBy = "terraform", Purpose = "davdeploy-module-validation", TestId = var.test_id }
}

module "queue" {
  source = "../../modules/sqs-queue"
  name   = local.name
  tags   = local.tags
}

module "events" {
  source = "../../modules/eventbridge-bus"
  name   = local.name
  tags   = local.tags
}

module "notifications" {
  source = "../../modules/sns-notifications"
  name   = local.name
  tags   = local.tags
}

output "queue_url" { value = module.queue.url }
output "bus_arn" { value = module.events.arn }
output "topic_arn" { value = module.notifications.arn }
