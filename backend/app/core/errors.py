from typing import Any, Optional

from fastapi import HTTPException


class AppError(HTTPException):
    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        super().__init__(status_code=http_status, detail=message)
        self.code = code
        self.message = message
        self.http_status = http_status


def error_response(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "error": {"code": code, "message": message}}


def success_response(data: Any = None) -> dict[str, Any]:
    return {"success": True, "data": data}


class NotFoundError(AppError):
    def __init__(self, entity: str = "Record") -> None:
        super().__init__("NOT_FOUND", f"{entity} not found", 404)


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action") -> None:
        super().__init__("PERMISSION_DENIED", message, 403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Invalid or missing credentials") -> None:
        super().__init__("UNAUTHORIZED", message, 401)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("CONFLICT", message, 409)


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("VALIDATION_ERROR", message, 422)