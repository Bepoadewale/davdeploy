variable "region" {
  type    = string
  default = "us-east-1"
}

variable "test_id" {
  type = string
}

variable "model_data_url" {
  type        = string
  description = "S3 URI of the disposable XGBoost model artifact uploaded by the certification script."
}
