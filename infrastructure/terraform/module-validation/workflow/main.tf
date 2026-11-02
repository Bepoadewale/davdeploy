variable "test_id" { type = string }

locals {
  name = "davdeploy-${var.test_id}"
  tags = {
    ManagedBy = "terraform"
    Purpose   = "davdeploy-module-validation"
    TestId    = var.test_id
  }
}

data "aws_iam_policy_document" "assume_states" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "step_functions" {
  name               = "${local.name}-step-functions"
  assume_role_policy = data.aws_iam_policy_document.assume_states.json
  tags               = local.tags
}

module "step_functions" {
  source   = "../../modules/step-functions"
  name     = local.name
  role_arn = aws_iam_role.step_functions.arn
  definition = jsonencode({
    Comment = "Disposable DavDeploy module validation"
    StartAt = "Succeed"
    States  = { Succeed = { Type = "Succeed" } }
  })
  tags = local.tags
}

output "state_machine_arn" { value = module.step_functions.arn }
