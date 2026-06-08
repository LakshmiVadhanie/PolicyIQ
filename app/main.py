"""
PolicyIQ — FastAPI Application Entry Point
Assembles all routes, middleware, and lifecycle hooks.
Deployed on GCP Cloud Run via Docker.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from structlog.stdlib import LoggerFactory

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health, chat, webhook
from app.config import settings

#  Structured logging setup 
logging.basicConfig(level=logging.INFO, format="%(message)s")

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


#  Lifespan 

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup and shutdown events."""
    logger.info(
        "policyiq_starting",
        environment=settings.app_env,
        mock_llm=settings.use_mock_llm,
        mock_bigquery=settings.use_mock_bigquery,
        gcp_project=settings.gcp_project_id,
    )
    # Pre-warm the LangGraph pipeline
    from app.agents.graph import get_graph
    get_graph()
    logger.info("langgraph_pipeline_initialized")
    yield
    logger.info("policyiq_shutting_down")


#  FastAPI App 

app = FastAPI(
    title="PolicyIQ",
    description=(
        "Agentic Insurance Intelligence Agent — powered by LangGraph multi-agent pipeline, "
        "Vertex AI Gemini, Dialogflow CX, and BigQuery analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


#  CORS Middleware 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else ["https://policyiq.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#  Request Logging Middleware 

@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Log all requests with timing and status."""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    request.state.request_id = request_id

    logger.info(
        "request_started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown",
    )

    response = await call_next(request)

    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "request_completed",
        request_id=request_id,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Latency-MS"] = str(latency_ms)
    return response


#  Exception Handler 

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


#  Register Routes 

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(webhook.router)
