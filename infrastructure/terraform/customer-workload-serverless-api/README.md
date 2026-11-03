# Customer serverless API renderer

This root is invoked only by the checked-in bounded runner. It creates one
Lambda function and one HTTP API from an immutable ZIP artifact under the
approved customer role. It accepts no free-form Terraform or IAM input.
