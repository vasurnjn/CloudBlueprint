# CloudBlueprint Implementation Plan

## Current Project State

The project directory is currently empty and is not initialized as a Git repository. This gives the MVP a clean starting point with no existing application structure to preserve.

This first task intentionally stops at planning. No application code, API routes, UI, database schema, tests, Docker files, or Terraform generation code will be implemented until the plan is approved.

## Proposed Folder Structure

```text
CloudBlueprint/
    PLAN.md
    README.md
    pyproject.toml
    docker-compose.yml
    Dockerfile.backend
    Dockerfile.frontend
    .gitignore

    cloudblueprint/
        __init__.py

        backend/
            __init__.py
            main.py

            api/
                __init__.py
                routes.py
                schemas.py

            models/
                __init__.py
                resource.py
                relationships.py
                graph.py
                architecture.py

            services/
                __init__.py
                architecture_service.py
                validation_service.py
                terraform_service.py

            validators/
                __init__.py
                base.py
                engine.py
                networking.py
                compute.py
                database.py
                dependency.py

            generators/
                __init__.py
                terraform/
                    __init__.py
                    generator.py
                    blocks.py
                    naming.py
                    files.py

            database/
                __init__.py
                connection.py
                models.py
                repository.py

        frontend/
            __init__.py
            app.py
            api_client.py
            components/
                __init__.py
                resource_form.py
                relationship_form.py
                validation_panel.py
                terraform_viewer.py

    tests/
        __init__.py
        test_resources.py
        test_graph.py
        test_validation.py
        test_terraform_generation.py
        test_api.py

    examples/
        valid_architecture.json
        invalid_architecture.json

    terraform_output/
        .gitkeep

    docs/
        architecture.md
```

### Structure Rationale

- `cloudblueprint/backend/models` owns the infrastructure domain model and graph representation.
- `cloudblueprint/backend/validators` owns validation rules and the validation engine.
- `cloudblueprint/backend/generators/terraform` owns Terraform rendering and file organization.
- `cloudblueprint/backend/services` coordinates core workflows without placing business logic in API handlers.
- `cloudblueprint/backend/api` exposes the FastAPI contract.
- `cloudblueprint/backend/database` owns SQLite persistence.
- `cloudblueprint/frontend` contains the Streamlit UI and API client only.
- `examples` contains importable architecture examples for tests, documentation, and demos.
- `terraform_output` is the default local destination for generated Terraform files.
- `docs` contains deeper technical architecture documentation.

## Internal Infrastructure Resource Model

The MVP should represent AWS resources using typed Pydantic models.

### Core Resource Fields

Every resource should share a common base model:

```text
Resource
    id: str
    name: str
    type: ResourceType
    properties: dict[str, Any]
    tags: dict[str, str]
```

`id` should be a stable user-facing identifier used for relationships and Terraform naming. It should be unique within an architecture.

`name` should be a display name.

`type` should be an enum, initially:

```text
VPC
PUBLIC_SUBNET
PRIVATE_SUBNET
SECURITY_GROUP
INTERNET_GATEWAY
EC2_INSTANCE
APPLICATION_LOAD_BALANCER
RDS_DATABASE
S3_BUCKET
```

`properties` should hold resource-specific configuration while the MVP is still small. This keeps resource creation flexible without introducing a large class hierarchy too early.

Examples:

```text
VPC:
    cidr_block

Subnet:
    cidr_block
    availability_zone

Security Group:
    ingress_rules
    egress_rules

EC2 Instance:
    ami
    instance_type

RDS Database:
    engine
    instance_class
    allocated_storage
    publicly_accessible

S3 Bucket:
    versioning_enabled
```

### Architecture Model

An architecture should be represented as:

```text
InfrastructureArchitecture
    id: str
    name: str
    resources: dict[str, Resource]
    relationships: list[Relationship]
```

This keeps the complete design serializable for API requests, examples, tests, SQLite persistence, and Terraform generation.

## Resource Relationship Representation

Relationships should be explicit typed edges between resource IDs:

```text
Relationship
    source_id: str
    target_id: str
    type: RelationshipType
```

Initial relationship types:

```text
BELONGS_TO
ATTACHES_TO
CONNECTS_TO
USES_SECURITY_GROUP
ROUTES_TO
TARGETS
DEPENDS_ON
```

Examples:

```text
public_subnet_1 BELONGS_TO vpc_main
private_subnet_1 BELONGS_TO vpc_main
internet_gateway_1 ATTACHES_TO vpc_main
ec2_web_1 BELONGS_TO public_subnet_1
ec2_web_1 USES_SECURITY_GROUP sg_web
alb_public TARGETS ec2_web_1
rds_main BELONGS_TO private_subnet_1
```

### Graph Design

Use a small internal graph wrapper instead of exposing a third-party graph library throughout the codebase.

Recommended MVP approach:

- Store resources and relationships in the `InfrastructureArchitecture` Pydantic model.
- Build an `InfrastructureGraph` helper from the architecture.
- Provide methods such as:
  - `get_resource(resource_id)`
  - `get_relationships(resource_id=None, relationship_type=None)`
  - `get_parents(resource_id, relationship_type=None)`
  - `get_children(resource_id, relationship_type=None)`
  - `has_path(source_id, target_id)`
  - `detect_cycles()`
  - `validate_references()`

NetworkX can be deferred unless graph traversal becomes meaningfully complex. A simple adjacency map should be easier to test, serialize, and reason about for the MVP.

## Validation Rule Architecture

The validation system should be rule-based and extensible.

### Validation Result Model

```text
ValidationResult
    rule_id: str
    rule_name: str
    severity: Severity
    resource_id: str | None
    description: str
    recommendation: str
```

Severity enum:

```text
INFO
WARNING
ERROR
CRITICAL
```

### Rule Interface

Each validation rule should implement a common protocol or abstract base class:

```text
ValidationRule
    rule_id: str
    name: str
    description: str
    severity: Severity
    validate(architecture, graph) -> list[ValidationResult]
```

Rules should be small, deterministic, and independently testable.

### Validation Engine

The validation engine should:

1. Build an `InfrastructureGraph` from the architecture.
2. Run reference integrity checks first.
3. Run all registered validation rules.
4. Return structured results.
5. Expose a helper such as `has_blocking_errors(results)` for Terraform generation.

Terraform generation should be blocked when results contain `ERROR` or `CRITICAL`.

### Initial Validation Rules

```text
REF001: Relationship references must point to existing resources.
NET001: Subnets must belong to a VPC.
NET002: Internet Gateway must attach to a VPC.
NET003: Internet-facing resources must have valid public networking.
CMP001: EC2 instances must belong to a subnet.
CMP002: EC2 instances should use at least one Security Group.
LB001: Application Load Balancer must target at least one EC2 instance.
DB001: RDS databases must belong to a private subnet.
DB002: RDS databases should not be publicly accessible by default.
DEP001: Circular dependencies must not exist.
```

## Terraform Generation Architecture

Terraform generation should be isolated in `cloudblueprint/backend/generators/terraform`.

### Core Generator Responsibilities

The Terraform generator should:

1. Accept a validated `InfrastructureArchitecture`.
2. Build an `InfrastructureGraph`.
3. Convert each supported resource into Terraform block objects.
4. Resolve references through relationships.
5. Group Terraform blocks into logical files.
6. Return generated files as an in-memory structure.
7. Optionally write generated files to `terraform_output`.

### Terraform File Model

```text
TerraformFile
    filename: str
    content: str

TerraformGenerationResult
    files: list[TerraformFile]
```

### Block Rendering

Avoid scattering string concatenation across the codebase. Use a small block-rendering layer:

```text
TerraformBlock
    block_type: str
    labels: list[str]
    attributes: dict[str, TerraformValue]
    nested_blocks: list[TerraformBlock]
```

The renderer should be responsible for indentation, quoting, lists, maps, nested blocks, and references.

### Generated Files

Initial file grouping:

```text
provider.tf
variables.tf
network.tf
compute.tf
database.tf
storage.tf
outputs.tf
```

### Initial Terraform Resource Mapping

```text
VPC -> aws_vpc
PUBLIC_SUBNET -> aws_subnet with map_public_ip_on_launch = true
PRIVATE_SUBNET -> aws_subnet with map_public_ip_on_launch = false
SECURITY_GROUP -> aws_security_group
INTERNET_GATEWAY -> aws_internet_gateway
EC2_INSTANCE -> aws_instance
APPLICATION_LOAD_BALANCER -> aws_lb, aws_lb_target_group, aws_lb_target_group_attachment
RDS_DATABASE -> aws_db_subnet_group, aws_db_instance
S3_BUCKET -> aws_s3_bucket
```

Where exact Terraform details become too broad for the MVP, prefer conservative minimal valid Terraform over half-modeled advanced behavior.

## FastAPI Endpoints Required For MVP

The API should expose architecture workflows and avoid putting domain logic inside route handlers.

### Health

```text
GET /health
```

Returns service status.

### Architectures

```text
POST /architectures
GET /architectures
GET /architectures/{architecture_id}
PUT /architectures/{architecture_id}
DELETE /architectures/{architecture_id}
```

Create, list, retrieve, update, and delete architecture documents.

### Resources

```text
POST /architectures/{architecture_id}/resources
PUT /architectures/{architecture_id}/resources/{resource_id}
DELETE /architectures/{architecture_id}/resources/{resource_id}
```

Manage resources within an architecture.

### Relationships

```text
POST /architectures/{architecture_id}/relationships
DELETE /architectures/{architecture_id}/relationships
```

Add and remove typed relationships.

### Validation

```text
POST /architectures/{architecture_id}/validate
```

Runs validation and returns structured validation results.

### Terraform

```text
POST /architectures/{architecture_id}/terraform
GET /architectures/{architecture_id}/terraform
```

Generate Terraform for a valid architecture and retrieve the latest generated files.

### Examples

```text
POST /examples/valid
POST /examples/invalid
```

Load starter example architectures into persistence for demos and testing.

## Streamlit MVP Interface

The UI should be functional and simple.

Initial views:

```text
Architecture selector
Resource editor
Relationship editor
Architecture graph summary
Validation results panel
Terraform generation and file viewer
```

The Streamlit UI should call the FastAPI backend through an `api_client.py` module. It should not import validators, generators, or database repositories directly.

## SQLite Persistence Design

For the MVP, persistence can store each architecture as a serialized JSON document.

Recommended initial schema:

```text
architectures
    id TEXT PRIMARY KEY
    name TEXT NOT NULL
    document_json TEXT NOT NULL
    created_at TEXT NOT NULL
    updated_at TEXT NOT NULL

terraform_generations
    id TEXT PRIMARY KEY
    architecture_id TEXT NOT NULL
    files_json TEXT NOT NULL
    created_at TEXT NOT NULL
```

This keeps the MVP simple while preserving the option to normalize resources and relationships later.

## MVP Implementation Phases

### Phase 1: Project Foundation

- Create Python package structure.
- Add dependency configuration.
- Add basic test configuration.
- Add `.gitignore`.
- Add initial README skeleton.

Verification:

- Import package successfully.
- Run an empty or smoke test suite.

### Phase 2: Infrastructure Domain Model

- Implement resource, relationship, architecture, and graph models.
- Add graph traversal helpers.
- Add reference and cycle detection.
- Add valid and invalid example architecture JSON files.

Verification:

- Unit tests for resource creation.
- Unit tests for relationship lookup.
- Unit tests for missing references and cycle detection.

### Phase 3: Validation Engine

- Implement validation result models.
- Implement rule base class.
- Implement validation engine.
- Implement initial validation rules.

Verification:

- Valid example has no blocking errors.
- Invalid example triggers multiple expected rules.
- Each rule has focused unit coverage.

### Phase 4: Terraform Generator

- Implement Terraform block model and renderer.
- Implement resource-specific Terraform generation.
- Implement logical file grouping.
- Block generation when validation has `ERROR` or `CRITICAL` results.

Verification:

- Generated files include expected Terraform resources.
- Generated references are stable and correct.
- Invalid architecture cannot generate Terraform.

### Phase 5: FastAPI Backend

- Implement API schemas.
- Implement architecture service.
- Implement validation and Terraform services.
- Add API routes.
- Add local in-memory behavior first if needed, then wire SQLite.

Verification:

- API tests with FastAPI test client.
- End-to-end flow: create architecture, add resources, add relationships, validate, generate Terraform.

### Phase 6: SQLite Persistence

- Add SQLite connection and repository layer.
- Persist architecture JSON documents.
- Persist Terraform generation outputs.
- Ensure services use repositories instead of in-memory state.

Verification:

- Repository tests using temporary SQLite database.
- API data persists across service object lifetimes.

### Phase 7: Streamlit UI

- Build basic UI for architecture selection.
- Add forms for resources and relationships.
- Add validation panel.
- Add Terraform generation/file viewer.

Verification:

- Manual local workflow through UI.
- UI can load valid and invalid examples through backend.

### Phase 8: Dockerization And Documentation

- Add backend Dockerfile.
- Add frontend Dockerfile.
- Add Docker Compose.
- Complete README.
- Add `docs/architecture.md`.

Verification:

- Run backend and frontend with Docker Compose.
- Confirm documented local and Docker workflows work.

## Technical Risks And Design Decisions

### Terraform Completeness

AWS Terraform resources can become detailed quickly, especially ALB and RDS. The MVP should generate minimal readable Terraform for representative architectures, not attempt to cover every production option.

Decision:

- Use conservative defaults.
- Keep resource properties explicit and small.
- Document unsupported advanced options.

### Public Networking Semantics

Determining whether a resource is internet-facing requires interpreting multiple relationships and properties.

Decision:

- For the MVP, classify `PUBLIC_SUBNET` as public by type.
- Require internet-facing ALBs to be associated with public subnets through relationships.
- Require RDS to belong to `PRIVATE_SUBNET`.

### Relationship Direction

Graph rules become simpler if relationship direction is consistent.

Decision:

- Use child-to-parent direction for containment-like relationships, such as `subnet BELONGS_TO vpc`.
- Use source-to-target direction for connection-like relationships, such as `alb TARGETS ec2`.

### Pydantic Version

FastAPI now commonly uses Pydantic v2, but some examples online still use v1 patterns.

Decision:

- Use Pydantic v2 unless an installed dependency constraint forces otherwise.

### Persistence Granularity

Normalizing every resource and relationship into relational tables would add complexity early.

Decision:

- Store architecture documents as JSON in SQLite for the MVP.
- Revisit normalization only if querying individual resources becomes a core requirement.

### Graph Library Choice

NetworkX is useful but may be unnecessary for this MVP.

Decision:

- Start with a small internal graph wrapper.
- Add NetworkX only if cycle detection, traversal, or visualization needs become complex.

### UI Scope

Streamlit can become awkward for graph editing if the interaction model is too ambitious.

Decision:

- Keep the MVP UI form-based.
- Display architecture as resource and relationship tables initially.
- Defer drag-and-drop diagram editing.

## Definition Of MVP Done

The MVP is complete when a user can:

1. Run the backend locally.
2. Run the Streamlit frontend locally.
3. Create or load an architecture.
4. Add supported AWS resources.
5. Define typed relationships between resources.
6. Run validation and see structured results.
7. Generate Terraform only for architectures without blocking validation issues.
8. View generated Terraform grouped by file.
9. Run automated tests for models, graph behavior, validation, and Terraform generation.
10. Read documentation explaining setup, architecture, supported resources, validation rules, and future improvements.
