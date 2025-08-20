from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
import logging

logger = logging.getLogger(__name__)

class CustomHTTPException(HTTPException):
    def __init__(self, status_code: int, detail: str, error_code: str = None):
        super().__init__(status_code, detail)
        self.error_code = error_code

async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Database error occurred",
            "error_code": "DATABASE_ERROR",
            "request_id": getattr(request.state, "request_id", None)
        }
    )

async def redis_exception_handler(request: Request, exc: RedisError):
    logger.error(f"Redis error: {exc}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Cache service unavailable",
            "error_code": "CACHE_ERROR",
            "request_id": getattr(request.state, "request_id", None)
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "request_id": getattr(request.state, "request_id", None)
        }
    )