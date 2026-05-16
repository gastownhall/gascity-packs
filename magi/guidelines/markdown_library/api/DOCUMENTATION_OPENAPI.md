# Documentation Standards (OpenAPI 3.1)

### OpenAPI Specification

Document all APIs using **OpenAPI 3.1.0**. Required sections:

| Section | Purpose |
|:--------|:--------|
| `info` | API metadata (title, version, description, contact) |
| `servers` | Server URLs (production, staging) |
| `paths` | All endpoints with parameters, request/response schemas |
| `components` | Reusable schemas, responses, parameters, security schemes |
| `security` | Authentication schemes |

### Reference Structure

```yaml
openapi: 3.1.0
info:
  title: Example API
  version: 1.0.0
  description: API description
  contact:
    email: api@example.com
servers:
  - url: https://api.example.com/v1
    description: Production
paths:
  /users:
    get:
      summary: List users
      operationId: listUsers
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserList'
components:
  schemas:
    User:
      type: object
      properties:
        id:
          type: string
        email:
          type: string
          format: email
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

### Documentation Completeness

Every endpoint must include:
- All parameters specified with types
- All response codes documented
- Request/response schemas defined
- Examples for common operations
- Error response schemas

### Documentation Content Beyond OpenAPI

- Authentication guide with working examples
- Quick start tutorial for common use cases
- Endpoint reference with all parameters
- Data type reference with field descriptions
- Error code reference with resolution guidance
- Rate limit documentation
- Versioning and deprecation policy
- Changelog for each version

### Documentation Examples

Required example types:
- `curl` examples for all operations
- SDK code snippets (one per supported language)
- Request/response pairs
- Error response examples

### Interactive Documentation

Recommended:
- Swagger UI or similar
- Sandbox environment for testing
- API key generation for sandbox
- "Try it now" functionality

### Documentation Maintenance

- Generate documentation from the OpenAPI specification
- Keep specification in sync with implementation (automated validation in CI)
- Version documentation alongside API versions
- Include runnable examples

---
[Back to Overview](./OVERVIEW.md)
