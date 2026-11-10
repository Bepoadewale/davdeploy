variable "region" {
  type        = string
  description = "AWS region for the public CloudFormation-template bucket."
}

variable "bucket_name" {
  type        = string
  description = "Globally unique bucket name. This bucket serves only public, non-secret CloudFormation templates."
}

variable "retained_template_keys" {
  type = set(string)
  # Previously published immutable templates remain available to existing
  # customer stacks and setup links. Append the formerly-current key before
  # publishing each later template revision.
  default = [
    "cloudformation/customer-discovery-role-600858c0ab944fd3f5aef06626ec5bc6ef9ed46352b418d87d651e05196bc11d.yaml",
    "cloudformation/customer-discovery-role-0e3209bff02286acf582ec3ed73858266261b294ae0c7e0d30ae37550a8926b2.yaml",
  ]
  description = "Immutable public template keys retained for existing CloudFormation stacks and setup links."

  validation {
    condition     = alltrue([for key in var.retained_template_keys : can(regex("^cloudformation/customer-discovery-role-[0-9a-f]{64}\\.yaml$", key))])
    error_message = "Retained template keys must be immutable customer-discovery-role CloudFormation object keys."
  }
}
