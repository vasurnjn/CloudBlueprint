# CloudBlueprint

CloudBlueprint is a cloud infrastructure design, validation, and Terraform generation platform focused on AWS architecture modeling.

## Current Implementation Status

This repository implements the following MVP features:

- Infrastructure resource and relationship models
- Graph-based architecture traversal & lookup
- Extensible validation rule engine (rules NET001-NET005, DB001-DB002, CMP001-CMP002, LB001, DEP001, REF001)
- Terraform block rendering layer (HCL syntax)
- Coherent AWS Terraform HCL generation for supported MVP AWS resources
- FastAPI backend exposing CRUD operations and services
- SQLite persistence storing architectures and generations
- Streamlit frontend providing an interactive designer UI
- Full automated test suite (Pytest)

The following planned phases are not implemented yet:

- Docker and Docker Compose (Phase 8)
- AWS deployment or provisioning
- Authentication

## Supported AWS Resource Types

- VPC
- Public Subnet
- Private Subnet
- Security Group
- Internet Gateway
- EC2 Instance
- Application Load Balancer
- RDS Database
- S3 Bucket

## Validation Rules & Diagnostics

The validation engine runs checking rules across the architecture topology graph. Terraform generation is strictly blocked when the engine returns `ERROR` or `CRITICAL` results.
* **NET001**: Subnets must belong to a VPC.
* **NET002**: Internet Gateways must attach to a VPC.
* **NET003**: Internet-facing load balancers must connect to public subnets in at least two distinct Availability Zones.
* **NET004**: Security Groups must belong to a VPC.
* **NET005**: VPCs containing public subnets must have an Internet Gateway attached.
* **DB001**: RDS databases must belong to at least two private subnets in distinct Availability Zones.
* **DB002**: RDS databases should not be publicly accessible (Warning).
* **CMP001/002**: EC2 instances must belong to a subnet and use at least one Security Group.
* **LB001**: Load balancers must target at least one EC2 instance.
* **DEP001/REF001**: Cycle detection and reference integrity checks.

## Local Development

Install the package and dependencies:

```powershell
python -m pip install -e .
```

Run tests:

```powershell
python -m pytest
```

### Running the Services

You can run the CloudBlueprint services either locally or using Docker Compose.

#### Option 1: Local Development

1. **Start the FastAPI Backend:**
   ```powershell
   python -m uvicorn cloudblueprint.backend.main:app --host 127.0.0.1 --port 8000
   ```
   The backend will start on `http://127.0.0.1:8000`. You can access the auto-generated API documentation at `http://127.0.0.1:8000/docs`.

2. **Start the Streamlit Frontend:**
   ```powershell
   python -m streamlit run cloudblueprint/frontend/app.py --server.port 8501 --server.address 127.0.0.1
   ```
   The frontend will be available at `http://127.0.0.1:8501`.

#### Option 2: Docker Compose

You can build and start the entire stack using Docker Compose:

```powershell
docker compose up --build
```

* **Streamlit Interface:** `http://localhost:8501`
* **FastAPI Backend:** `http://localhost:8000`
* **Auto-generated API docs:** `http://localhost:8000/docs`

To stop the services and clean up the containers:

```powershell
docker compose down
```

The SQLite database is persistently stored in a named Docker volume (`sqlite_data`) mounted at `/data` inside the backend container.


### Application Workflow (UI Sections)

The Streamlit UI organizes your infrastructure workspace into four workflow phases:

1. **DESIGN (Resources):** Create or select an architecture. Add and configure cloud resources (VPCs, subnets, EC2s, RDS, etc.) with explicit attributes and tags. A dynamic read-only visual topology diagram is rendered automatically based on your resources and connections.
2. **CONNECT (Relationships):** Define directed connections between resources (e.g. subnets `BELONGS_TO` VPC, load balancer `TARGETS` EC2).
3. **VALIDATE (Diagnostics):** Trigger backend diagnostics to discover architectural faults, missing linkages, and security warnings.
4. **GENERATE (Terraform):** Generate syntax-valid Terraform HCL files (`provider.tf`, `variables.tf`, `network.tf`, `compute.tf`, `database.tf`, `storage.tf`, `outputs.tf`). View them in tabs or download them as an assembled ZIP archive.

## Terraform MVP Limitations & Constraints

* **No Production Readiness:** Generated configurations are intended for learning, visual mapping, and scaffolding. They are not production-ready or hardened.
* **No Provisioning/Deployment:** CloudBlueprint does not run `terraform apply` or configure AWS accounts. All actions are offline/local.
* **Placeholder AMIs:** EC2 instances generate placeholder AMI IDs (or reference a variable). Users must replace these with valid, region-specific AMIs before executing Terraform.
* **No NAT Gateway support:** Private subnets are modeled without NAT Gateways or egress routing. Outbound internet access for private resources is not supported or generated.
* **RDS & ALB requirements:** Load Balancers require at least two public subnets, and RDS databases require at least two private subnets in distinct Availability Zones to generate valid DB Subnet Groups and Load Balancer subnets.



