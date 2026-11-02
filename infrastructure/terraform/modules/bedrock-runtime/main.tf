variable "name" { type = string }
variable "allowed_model_arns" { type = list(string) }
variable "tags" { type = map(string) }

data "aws_iam_policy_document" "invoke" {
  statement {
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = var.allowed_model_arns
  }
}

resource "aws_bedrock_guardrail" "this" {
  name                      = var.name
  blocked_input_messaging   = "This request cannot be processed."
  blocked_outputs_messaging = "This response cannot be returned."
  description               = "DavDeploy guardrail for ${var.name}"
  tags                      = var.tags
}

output "invoke_policy_json" { value = data.aws_iam_policy_document.invoke.json }
output "guardrail_id" { value = aws_bedrock_guardrail.this.guardrail_id }
