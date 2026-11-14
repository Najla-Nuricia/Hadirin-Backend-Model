"""FastAPI application entrypoint registering routers, middleware, and exception handlers."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, dosen, health, kelas, mahasiswa, pengajuan, presensi, wajah
from app.core.config import get_settings
from app.core.exceptions import AppException


def create_app() -> FastAPI:
    """Create and configure the Hadirin Backend FastAPI instance."""
    settings = get_settings()

    application = FastAPI(
        title="Hadirin Backend API",
        version="2.0.0",
        description="Backend REST API & Face Recognition Service untuk Sistem Presensi Hadirin.",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
        )

    # Register specific `/mahasiswa/*` routers before `/{nim}` in `mahasiswa.router`.
    @application.get("/", tags=["Root"])
    async def root_index() -> dict[str, str]:
        return {
            "name": "Hadirin Backend API",
            "version": "2.0.0",
            "status": "online",
            "docs": "/docs",
        }

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(kelas.router)
    application.include_router(dosen.router)
    application.include_router(pengajuan.router)
    application.include_router(wajah.router)
    application.include_router(mahasiswa.router)
    application.include_router(presensi.router)

    return application


app = create_app()
