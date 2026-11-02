variable "domain" { type = string }
variable "tags" { type = map(string) }

resource "aws_ses_domain_identity" "this" {
  domain = var.domain
}

resource "aws_ses_domain_dkim" "this" {
  domain = aws_ses_domain_identity.this.domain
}

resource "aws_ses_domain_mail_from" "this" {
  domain           = aws_ses_domain_identity.this.domain
  mail_from_domain = "mail.${aws_ses_domain_identity.this.domain}"
}

output "verification_token" { value = aws_ses_domain_identity.this.verification_token }
output "dkim_tokens" { value = aws_ses_domain_dkim.this.dkim_tokens }
