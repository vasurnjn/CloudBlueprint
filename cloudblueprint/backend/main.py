from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cloudblueprint.backend.api.routes import router
from cloudblueprint.backend.database.repository import (
    SQLiteArchitectureRepository,
    SQLiteTerraformGenerationRepository,
)
from cloudblueprint.backend.services.architecture_service import ArchitectureService
from cloudblueprint.backend.services.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    TerraformGenerationBlockedError,
)
from cloudblueprint.backend.services.terraform_service import TerraformService
from cloudblueprint.backend.services.validation_service import ValidationService


def create_app(database_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="CloudBlueprint API", version="0.1.0")

    architecture_repository = SQLiteArchitectureRepository(database_path)
    terraform_repository = SQLiteTerraformGenerationRepository(database_path)

    app.state.architecture_service = ArchitectureService(architecture_repository)
    app.state.validation_service = ValidationService(architecture_repository)
    app.state.terraform_service = TerraformService(
        architecture_repository,
        terraform_repository,
    )

    register_exception_handlers(app)
    app.include_router(router)
    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(
        request: Request,
        exception: NotFoundError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exception)},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(
        request: Request,
        exception: ConflictError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exception)},
        )

    @app.exception_handler(TerraformGenerationBlockedError)
    async def terraform_blocked_handler(
        request: Request,
        exception: TerraformGenerationBlockedError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": str(exception),
                "validation_results": [
                    result.model_dump(mode="json")
                    for result in exception.validation_results
                ],
            },
        )

    @app.exception_handler(BadRequestError)
    async def bad_request_handler(
        request: Request,
        exception: BadRequestError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exception)},
        )


app = create_app()
