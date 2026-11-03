data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  name                = "dd${replace(var.test_id, "-", "")}"
  embedding_model_arn = "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-embed-text-v2:0"
  tags                = { ManagedBy = "terraform", Purpose = "davdeploy-module-validation", TestId = var.test_id }
}

resource "aws_s3_bucket" "documents" {
  bucket        = "davdeploy-${var.test_id}-kb-documents"
  force_destroy = true
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "document" {
  bucket                 = aws_s3_bucket.documents.id
  key                    = "source/davdeploy-certification.txt"
  content                = "DavDeploy certification document: retrieval evidence confirms this exact synthetic phrase."
  server_side_encryption = "AES256"
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "knowledge_base" {
  name               = "${local.name}-kb"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "knowledge_base" {
  statement {
    actions   = ["bedrock:InvokeModel"]
    resources = [local.embedding_model_arn]
  }
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.documents.arn}/source/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.documents.arn]
  }
  statement {
    actions   = ["aoss:APIAccessAll"]
    resources = [module.vector.arn]
  }
}

resource "aws_iam_role_policy" "knowledge_base" {
  name   = "${local.name}-kb"
  role   = aws_iam_role.knowledge_base.id
  policy = data.aws_iam_policy_document.knowledge_base.json
}

module "vector" {
  source            = "../../modules/opensearch-serverless-vector"
  name              = local.name
  principals        = [aws_iam_role.knowledge_base.arn, data.aws_caller_identity.current.arn]
  allow_from_public = true
  tags              = local.tags
}

module "knowledge_base" {
  count               = var.create_knowledge_base ? 1 : 0
  source              = "../../modules/bedrock-knowledge-base"
  name                = local.name
  role_arn            = aws_iam_role.knowledge_base.arn
  collection_arn      = module.vector.arn
  vector_index_name   = "bedrock-kb-index"
  embedding_model_arn = local.embedding_model_arn
  field_mapping = {
    vector_field   = "bedrock-vector"
    text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
    metadata_field = "AMAZON_BEDROCK_METADATA"
  }
  tags       = local.tags
  depends_on = [aws_iam_role_policy.knowledge_base, module.vector]
}

resource "aws_bedrockagent_data_source" "documents" {
  count                = var.create_knowledge_base ? 1 : 0
  knowledge_base_id    = module.knowledge_base[0].knowledge_base_id
  name                 = "${local.name}-source"
  data_deletion_policy = "DELETE"
  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = aws_s3_bucket.documents.arn
      inclusion_prefixes = ["source/"]
    }
  }
}

output "collection_id" { value = module.vector.id }
output "collection_endpoint" { value = module.vector.endpoint }
output "knowledge_base_id" { value = try(module.knowledge_base[0].knowledge_base_id, null) }
output "data_source_id" { value = try(aws_bedrockagent_data_source.documents[0].data_source_id, null) }
