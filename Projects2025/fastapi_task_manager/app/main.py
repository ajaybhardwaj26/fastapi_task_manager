from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from datetime import datetime
import logging

from app.api.v1.routes import user, task, comment, auth
from app.core.config import settings
from app.core.cache import cache
from app.db.session import AsyncSessionLocal
from sqlalchemy import select

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("task_manager.main")

app = FastAPI(
    title="Task Manager API",
    version="1.0.0",
    description="Production-grade task management API with JWT auth, RBAC, and caching"
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["1000/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Custom rate limit error response
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request, exc: RateLimitExceeded):
    logger.warning(f"Rate limit exceeded for {request.client.host}")
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after": exc.detail,
            "error_code": "RATE_LIMIT_EXCEEDED"
        },
        headers={"X-RateLimit-Reset": str(exc.detail)}
    )

# Database error handler
@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request, exc: SQLAlchemyError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Database error occurred",
            "error_code": "DATABASE_ERROR"
        }
    )

# Redis error handler
@app.exception_handler(RedisError)
async def redis_exception_handler(request, exc: RedisError):
    logger.error(f"Redis error: {exc}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Cache service temporarily unavailable",
            "error_code": "CACHE_ERROR"
        }
    )

# General exception handler
@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": "INTERNAL_ERROR"
        }
    )

# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "task-manager-api"
    }

@app.get("/health/ready")
async def readiness_check():
    """Readiness check - verify DB and Redis connections"""
    try:
        # Test DB connection
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))

        # Test Redis connection
        if cache.redis_client:
            await cache.redis_client.ping()
        else:
            await cache.connect()
            await cache.redis_client.ping()

        return {
            "status": "ready",
            "services": {"database": "ok", "redis": "ok"},
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(user.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(task.router, prefix="/api/v1/tasks", tags=["Tasks"])
app.include_router(comment.router, prefix="/api/v1/comments", tags=["Comments"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Task Manager API...")
    await cache.connect()
    logger.info("Cache connected successfully")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Task Manager API...")
    await cache.disconnect()
    logger.info("Cache disconnected successfully")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info",
        reload=settings.ENVIRONMENT == "development"
    )
