data "aws_caller_identity" "current" {}

locals {
  project_scope = "${var.connection_id}:${var.project_id}:${var.region}"
  project_hash  = substr(sha256(local.project_scope), 0, 20)
  table_name    = "davdeploy-${var.expected_account_id}-${var.region}-${local.project_hash}"

  tags = {
    ManagedBy           = "davdeploy"
    DavDeployConnection = var.connection_id
    DavDeployProject    = var.project_id
    DavDeployPlan       = var.plan_digest
    Scope               = "customer-workload"
  }
}

resource "terraform_data" "account_guard" {
  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.account_id == var.expected_account_id
      error_message = "The assumed customer role is not in the approved AWS account."
    }
  }
}

resource "aws_dynamodb_table" "this" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags       = local.tags
  depends_on = [terraform_data.account_guard]
}

output "table_name" { value = aws_dynamodb_table.this.name }
output "table_arn" { value = aws_dynamodb_table.this.arn }
