"""Domain exception hierarchy mapped to clean HTTP error responses."""

from fastapi import status


class AppException(Exception):
    """Base application exception with HTTP status code and error code."""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "app_error",
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.code = code


class BadRequestError(AppException):
    """Raised when input payload or business preconditions are invalid."""

    def __init__(self, detail: str, code: str = "bad_request") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST, code=code)


class UnauthorizedError(AppException):
    """Raised when credentials or bearer tokens are missing or invalid."""

    def __init__(self, detail: str = "Autentikasi gagal atau token tidak valid.", code: str = "unauthorized") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED, code=code)


class ForbiddenError(AppException):
    """Raised when the authenticated actor lacks access to a resource."""

    def __init__(self, detail: str = "Anda tidak memiliki izin untuk aksi ini.", code: str = "forbidden") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN, code=code)


class NotFoundError(AppException):
    """Raised when a requested entity does not exist."""

    def __init__(self, detail: str = "Data tidak ditemukan.", code: str = "not_found") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND, code=code)


class ConflictError(AppException):
    """Raised when creating or modifying an entity conflicts with existing state."""

    def __init__(self, detail: str = "Data sudah terdaftar.", code: str = "conflict") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT, code=code)


class UnprocessableError(AppException):
    """Raised when domain content cannot be processed (e.g. undetectable face)."""

    def __init__(self, detail: str, code: str = "unprocessable_entity") -> None:
        status_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        super().__init__(detail=detail, status_code=status_422, code=code)


class ExternalServiceError(AppException):
    """Raised when an upstream dependency (Supabase DB/Auth/Storage) fails."""

    def __init__(self, detail: str = "Gagal terhubung ke layanan eksternal.", code: str = "external_service_error") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_502_BAD_GATEWAY, code=code)


class ServiceUnavailableError(AppException):
    """Raised when a required service configuration is intentionally disabled."""

    def __init__(self, detail: str = "Layanan sementara tidak tersedia.", code: str = "service_unavailable") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, code=code)


