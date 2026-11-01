from pathlib import Path


def test_only_read_only_blog_routes_bypass_the_api_gateway_jwt_default_route():
    source = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()

    assert '"GET /api/v1/blog/posts"' in source
    assert '"GET /api/v1/blog/posts/{slug}"' in source
    assert '"GET /api/v1/blog/posts/{slug}/comments"' in source
    assert 'resource "aws_apigatewayv2_route" "public_blog_read"' in source
    assert "All writes, team authoring,\n# and comment changes continue through the JWT-protected" in source
