variable "name" { type = string }
variable "principals" { type = list(string) }
variable "allow_from_public" {
  type        = bool
  default     = false
  description = "Only true for an isolated disposable certification collection."
}
variable "tags" { type = map(string) }

resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${var.name}-encryption"
  type = "encryption"
  policy = jsonencode({
    Rules       = [{ ResourceType = "collection", Resource = ["collection/${var.name}"] }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name = "${var.name}-network"
  type = "network"
  policy = jsonencode([{
    Rules = [
      { ResourceType = "collection", Resource = ["collection/${var.name}"] },
      { ResourceType = "dashboard", Resource = ["collection/${var.name}"] },
    ]
    AllowFromPublic = var.allow_from_public
  }])
}

resource "aws_opensearchserverless_collection" "this" {
  name             = var.name
  type             = "VECTORSEARCH"
  standby_replicas = "DISABLED"
  tags             = var.tags
  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
  ]
}

resource "aws_opensearchserverless_access_policy" "this" {
  name = "${var.name}-data"
  type = "data"
  policy = jsonencode([{
    Description = "Scoped vector collection access for DavDeploy Knowledge Base lifecycle."
    Principal   = var.principals
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${var.name}"]
        Permission   = ["aoss:DescribeCollectionItems"]
      },
      {
        ResourceType = "index"
        Resource     = ["index/${var.name}/*"]
        Permission   = ["aoss:CreateIndex", "aoss:DescribeIndex", "aoss:ReadDocument", "aoss:WriteDocument", "aoss:UpdateIndex", "aoss:DeleteIndex"]
      },
    ]
  }])
  depends_on = [aws_opensearchserverless_collection.this]
}

output "arn" { value = aws_opensearchserverless_collection.this.arn }
output "id" { value = aws_opensearchserverless_collection.this.id }
output "endpoint" { value = aws_opensearchserverless_collection.this.collection_endpoint }
