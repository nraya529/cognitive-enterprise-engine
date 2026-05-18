from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from .agents.orchestrator import process_document
from .config import settings
from .logging_setup import configure_logging, get_logger, new_trace_id
from .models.schemas import ProcessedDocument, WebhookPayload
from .routes.prospecting import router as prospecting_router
from .services.document_parser import parse_payload
from .services.storage import close_storage, init_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    log = get_logger("startup")
    log.info("server_starting", extraction_model=settings.extraction_model)
    await init_storage()
    yield
    await close_storage()
    log.info("server_stopping")


app = FastAPI(
    title="Cognitive Enterprise Engine",
    description="Autonomous multi-agent system for back-office document processing.",
    version="0.1.0",
    lifespan=lifespan,
)
log = get_logger(__name__)
app.include_router(prospecting_router)


@app.middleware("http")
async def request_trace_middleware(request: Request, call_next):
    trace_id = new_trace_id()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled_request_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "trace_id": trace_id},
        )
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "extraction_model": settings.extraction_model}


@app.post("/webhook", response_model=ProcessedDocument)
async def webhook(payload: WebhookPayload) -> ProcessedDocument:
    if not payload.raw_text:
        raise HTTPException(status_code=400, detail="raw_text is required")
    try:
        return await process_document(payload.raw_text)
    except RuntimeError as e:
        log.exception("pipeline_failed")
        return JSONResponse(
            status_code=422,
            content={"error": "processing_failed", "detail": str(e)},
        )


@app.post("/upload", response_model=ProcessedDocument)
async def upload(file: UploadFile = File(...)) -> ProcessedDocument:
    content = await file.read()
    text = parse_payload(content, file.content_type or "text/plain")
    if not text.strip():
        raise HTTPException(status_code=400, detail="file produced no extractable text")
    try:
        return await process_document(text)
    except RuntimeError as e:
        log.exception("upload_pipeline_failed", filename=file.filename)
        return JSONResponse(
            status_code=422,
            content={"error": "processing_failed", "detail": str(e)},
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
