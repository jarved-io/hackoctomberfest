"""
FastAPI application for the API Hallucination Firewall backend.

Endpoints:
  GET  /health      — Service health check.
  POST /api/verify  — Verify Python code against trusted API references.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import APP_NAME, APP_VERSION, CORS_ORIGINS
from app.knowledge_base import KnowledgeBase
from app.schemas import (
    Metadata,
    OverallStatus,
    VerifyRequest,
    VerifyResponse,
)
from app.verifier import verify_code


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

knowledge_base = KnowledgeBase()


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hook (currently a no-op placeholder)."""
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="API Hallucination Firewall",
    description=(
        "Detects potentially hallucinated or incorrect Python API usage "
        "in AI-generated code using deterministic verification against "
        "trusted API reference data."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)

# -- CORS ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    """Return a clean 422 without exposing internals."""
    errors = []
    for err in exc.errors():
        errors.append({
            "field": " → ".join(str(loc) for loc in err.get("loc", [])),
            "message": err.get("msg", "Validation error"),
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception,
) -> JSONResponse:
    """Catch unhandled exceptions — never expose stack traces."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again."},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", summary="Health check")
async def health_check() -> dict:
    """Confirm the backend is running.

    Does **not** expose secrets, filesystem paths, or stack traces.
    """
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
    }


@app.post(
    "/api/verify",
    response_model=VerifyResponse,
    summary="Verify Python code against trusted API references",
    responses={
        422: {"description": "Validation error (bad request body)"},
    },
)
async def verify_endpoint(request: VerifyRequest) -> VerifyResponse:
    """Verify Python source code against a trusted API reference snapshot.

    The verification is fully deterministic and uses **no** AI model.
    """
    # Reject whitespace-only code (Pydantic min_length passes it)
    if not request.code.strip():
        return VerifyResponse(
            overallStatus=OverallStatus.ERROR,
            metadata=Metadata(
                library=request.library,
                version=request.version,
                warnings=["Submitted code is empty or whitespace-only."],
                snapshotCompleteness="n/a",
            ),
        )

    return verify_code(
        code=request.code,
        library=request.library,
        version=request.version,
        knowledge_base=knowledge_base,
    )
