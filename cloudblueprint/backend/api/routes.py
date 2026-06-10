from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from cloudblueprint.backend.api.schemas import (
    ArchitectureRequest,
    ArchitectureResponse,
    HealthResponse,
    RelationshipRequest,
    ResourceRequest,
    TerraformGenerationResponse,
    ValidationReportResponse,
)
from cloudblueprint.backend.services.architecture_service import ArchitectureService
from cloudblueprint.backend.services.terraform_service import TerraformService
from cloudblueprint.backend.services.validation_service import ValidationService


router = APIRouter()


def get_architecture_service(request: Request) -> ArchitectureService:
    return request.app.state.architecture_service


def get_validation_service(request: Request) -> ValidationService:
    return request.app.state.validation_service


def get_terraform_service(request: Request) -> TerraformService:
    return request.app.state.terraform_service


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post(
    "/architectures",
    response_model=ArchitectureResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_architecture(
    payload: ArchitectureRequest,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    record = service.create_architecture(payload)
    return ArchitectureResponse.from_record(record)


@router.get("/architectures", response_model=list[ArchitectureResponse])
def list_architectures(
    service: ArchitectureService = Depends(get_architecture_service),
) -> list[ArchitectureResponse]:
    return [
        ArchitectureResponse.from_record(record)
        for record in service.list_architectures()
    ]


@router.get("/architectures/{architecture_id}", response_model=ArchitectureResponse)
def get_architecture(
    architecture_id: str,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    return ArchitectureResponse.from_record(service.get_architecture(architecture_id))


@router.put("/architectures/{architecture_id}", response_model=ArchitectureResponse)
def update_architecture(
    architecture_id: str,
    payload: ArchitectureRequest,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    record = service.update_architecture(architecture_id, payload)
    return ArchitectureResponse.from_record(record)


@router.delete(
    "/architectures/{architecture_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_architecture(
    architecture_id: str,
    service: ArchitectureService = Depends(get_architecture_service),
) -> Response:
    service.delete_architecture(architecture_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/architectures/{architecture_id}/resources",
    response_model=ArchitectureResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_resource(
    architecture_id: str,
    payload: ResourceRequest,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    record = service.add_resource(architecture_id, payload)
    return ArchitectureResponse.from_record(record)


@router.put(
    "/architectures/{architecture_id}/resources/{resource_id}",
    response_model=ArchitectureResponse,
)
def update_resource(
    architecture_id: str,
    resource_id: str,
    payload: ResourceRequest,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    record = service.update_resource(architecture_id, resource_id, payload)
    return ArchitectureResponse.from_record(record)


@router.delete(
    "/architectures/{architecture_id}/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_resource(
    architecture_id: str,
    resource_id: str,
    service: ArchitectureService = Depends(get_architecture_service),
) -> Response:
    service.delete_resource(architecture_id, resource_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/architectures/{architecture_id}/relationships",
    response_model=ArchitectureResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_relationship(
    architecture_id: str,
    payload: RelationshipRequest,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    record = service.add_relationship(architecture_id, payload)
    return ArchitectureResponse.from_record(record)


@router.delete(
    "/architectures/{architecture_id}/relationships",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_relationship(
    architecture_id: str,
    payload: RelationshipRequest,
    service: ArchitectureService = Depends(get_architecture_service),
) -> Response:
    service.delete_relationship(architecture_id, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/architectures/{architecture_id}/validate",
    response_model=ValidationReportResponse,
)
def validate_architecture(
    architecture_id: str,
    service: ValidationService = Depends(get_validation_service),
) -> ValidationReportResponse:
    report = service.validate_architecture(architecture_id)
    return ValidationReportResponse.from_report(report)


@router.post(
    "/architectures/{architecture_id}/terraform",
    response_model=TerraformGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_terraform(
    architecture_id: str,
    service: TerraformService = Depends(get_terraform_service),
) -> TerraformGenerationResponse:
    record = service.generate_terraform(architecture_id)
    return TerraformGenerationResponse.from_record(record)


@router.get(
    "/architectures/{architecture_id}/terraform",
    response_model=TerraformGenerationResponse,
)
def get_latest_terraform(
    architecture_id: str,
    service: TerraformService = Depends(get_terraform_service),
) -> TerraformGenerationResponse:
    record = service.get_latest_terraform(architecture_id)
    return TerraformGenerationResponse.from_record(record)


@router.post(
    "/examples/valid",
    response_model=ArchitectureResponse,
    status_code=status.HTTP_201_CREATED,
)
def load_valid_example(
    response: Response,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    record, created = service.load_example("valid")
    if not created:
        response.status_code = status.HTTP_200_OK
    return ArchitectureResponse.from_record(record)


@router.post(
    "/examples/invalid",
    response_model=ArchitectureResponse,
    status_code=status.HTTP_201_CREATED,
)
def load_invalid_example(
    response: Response,
    service: ArchitectureService = Depends(get_architecture_service),
) -> ArchitectureResponse:
    record, created = service.load_example("invalid")
    if not created:
        response.status_code = status.HTTP_200_OK
    return ArchitectureResponse.from_record(record)

