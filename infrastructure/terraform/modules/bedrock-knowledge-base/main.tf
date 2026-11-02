variable "name" { type = string }
variable "role_arn" { type = string }
variable "collection_arn" { type = string }
variable "vector_index_name" { type = string }
variable "field_mapping" {
  type = object({
    metadata_field = string
    text_field     = string
    vector_field   = string
  })
}
variable "embedding_model_arn" { type = string }
variable "tags" { type = map(string) }

resource "aws_bedrockagent_knowledge_base" "this" {
  name     = var.name
  role_arn = var.role_arn
  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = var.embedding_model_arn
    }
  }
  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = var.collection_arn
      vector_index_name = var.vector_index_name
      field_mapping {
        metadata_field = var.field_mapping.metadata_field
        text_field     = var.field_mapping.text_field
        vector_field   = var.field_mapping.vector_field
      }
    }
  }
  tags = var.tags
}

output "knowledge_base_id" { value = aws_bedrockagent_knowledge_base.this.id }
