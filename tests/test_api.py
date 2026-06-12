from __future__ import annotations

from fastapi.testclient import TestClient

from cloudblueprint.backend.main import create_app
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(tmp_path / "api.sqlite"))


def _architecture_payload(architecture: InfrastructureArchitecture) -> dict:
    return architecture.model_dump(mode="json")


def test_api_health_endpoint(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_architecture_crud_endpoints(tmp_path) -> None:
    payload = {
        "id": "arch",
        "name": "Architecture",
        "resources": {},
        "relationships": [],
    }

    with _client(tmp_path) as client:
        create_response = client.post("/architectures", json=payload)
        list_response = client.get("/architectures")
        get_response = client.get("/architectures/arch")

        updated_payload = {**payload, "name": "Updated Architecture"}
        update_response = client.put("/architectures/arch", json=updated_payload)
        delete_response = client.delete("/architectures/arch")
        missing_response = client.get("/architectures/arch")

    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert [architecture["id"] for architecture in list_response.json()] == ["arch"]
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Architecture"
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Architecture"
    assert delete_response.status_code == 204
    assert missing_response.status_code == 404


def test_api_resource_relationship_validation_and_terraform_workflow(tmp_path) -> None:
    with _client(tmp_path) as client:
        create_response = client.post(
            "/architectures",
            json={
                "id": "workflow",
                "name": "Workflow Architecture",
                "resources": {},
                "relationships": [],
            },
        )
        add_vpc_response = client.post(
            "/architectures/workflow/resources",
            json={"id": "vpc", "name": "VPC", "type": "VPC"},
        )
        client.post(
            "/architectures/workflow/resources",
            json={
                "id": "public_subnet",
                "name": "Public Subnet",
                "type": "PUBLIC_SUBNET",
                "properties": {
                    "cidr_block": "10.0.1.0/24",
                    "availability_zone": "us-east-1a",
                },
            },
        )
        client.post(
            "/architectures/workflow/resources",
            json={"id": "igw", "name": "Internet Gateway", "type": "INTERNET_GATEWAY"},
        )
        client.post(
            "/architectures/workflow/relationships",
            json={
                "source_id": "public_subnet",
                "target_id": "vpc",
                "type": "BELONGS_TO",
            },
        )
        add_relationship_response = client.post(
            "/architectures/workflow/relationships",
            json={"source_id": "igw", "target_id": "vpc", "type": "ATTACHES_TO"},
        )

        get_response = client.get("/architectures/workflow")
        validate_response = client.post("/architectures/workflow/validate")
        generate_response = client.post("/architectures/workflow/terraform")
        latest_response = client.get("/architectures/workflow/terraform")

    assert create_response.status_code == 201
    assert add_vpc_response.status_code == 201
    assert add_relationship_response.status_code == 201
    assert get_response.status_code == 200
    assert len(get_response.json()["resources"]) == 3
    assert len(get_response.json()["relationships"]) == 2
    assert validate_response.status_code == 200
    assert validate_response.json()["is_valid"] is True
    assert validate_response.json()["results"] == []
    assert generate_response.status_code == 201
    assert "network.tf" in {
        terraform_file["filename"]
        for terraform_file in generate_response.json()["files"]
    }
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == generate_response.json()["id"]


def test_api_relationship_delete_endpoint(tmp_path) -> None:
    with _client(tmp_path) as client:
        client.post(
            "/architectures",
            json={
                "id": "arch",
                "name": "Architecture",
                "resources": {
                    "vpc": {"id": "vpc", "name": "VPC", "type": "VPC"},
                    "subnet": {
                        "id": "subnet",
                        "name": "Subnet",
                        "type": "PUBLIC_SUBNET",
                    },
                },
                "relationships": [
                    {
                        "source_id": "subnet",
                        "target_id": "vpc",
                        "type": "BELONGS_TO",
                    }
                ],
            },
        )
        delete_response = client.request(
            "DELETE",
            "/architectures/arch/relationships",
            json={"source_id": "subnet", "target_id": "vpc", "type": "BELONGS_TO"},
        )
        get_response = client.get("/architectures/arch")

    assert delete_response.status_code == 204
    assert get_response.json()["relationships"] == []


def test_api_validation_endpoint_uses_existing_engine(
    tmp_path,
    valid_architecture: InfrastructureArchitecture,
) -> None:
    with _client(tmp_path) as client:
        client.post("/architectures", json=_architecture_payload(valid_architecture))
        response = client.post(f"/architectures/{valid_architecture.id}/validate")

    assert response.status_code == 200
    assert response.json()["is_valid"] is True
    assert response.json()["results"] == []


def test_api_blocks_invalid_architecture_terraform_generation(
    tmp_path,
    invalid_architecture: InfrastructureArchitecture,
) -> None:
    with _client(tmp_path) as client:
        client.post("/architectures", json=_architecture_payload(invalid_architecture))
        response = client.post(f"/architectures/{invalid_architecture.id}/terraform")

    assert response.status_code == 400
    assert {result["rule_id"] for result in response.json()["validation_results"]} >= {
        "REF001",
        "DEP001",
    }


def test_api_example_loading_endpoints(tmp_path) -> None:
    with _client(tmp_path) as client:
        valid_response = client.post("/examples/valid")
        duplicate_valid_response = client.post("/examples/valid")
        invalid_response = client.post("/examples/invalid")
        validate_invalid_response = client.post("/architectures/invalid-web-app/validate")

    assert valid_response.status_code == 201
    assert valid_response.json()["id"] == "valid-web-app"
    assert duplicate_valid_response.status_code == 200
    assert invalid_response.status_code == 201
    assert invalid_response.json()["id"] == "invalid-web-app"
    assert validate_invalid_response.status_code == 200
    assert validate_invalid_response.json()["is_valid"] is False

