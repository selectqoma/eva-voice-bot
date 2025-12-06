"""Document management API endpoints."""

import tempfile
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ...config import get_settings
from ...rag.ingest import DocumentIngester

router = APIRouter()


class IngestResponse(BaseModel):
    """Response for document ingestion."""

    customer_id: str
    chunks_created: int
    message: str


class TextIngestRequest(BaseModel):
    """Request for ingesting raw text."""

    customer_id: str
    text: str
    source_name: str = "manual_entry"


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    customer_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload and ingest a document for a customer.

    Supported file types: PDF, TXT, CSV, DOCX, MD
    """
    settings = get_settings()

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in DocumentIngester.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Supported: {DocumentIngester.SUPPORTED_EXTENSIONS}",
        )

    ingester = DocumentIngester(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = Path(temp_file.name)

    try:
        chunks_created = await ingester.ingest_file(customer_id, temp_path)

        return IngestResponse(
            customer_id=customer_id,
            chunks_created=chunks_created,
            message=f"Successfully ingested {file.filename}",
        )
    finally:
        # Clean up temp file
        temp_path.unlink(missing_ok=True)


@router.post("/upload-multiple", response_model=IngestResponse)
async def upload_multiple_documents(
    customer_id: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """Upload and ingest multiple documents for a customer."""
    settings = get_settings()

    ingester = DocumentIngester(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    temp_paths: list[Path] = []
    total_chunks = 0

    try:
        # Save all files temporarily
        for file in files:
            if not file.filename:
                continue

            suffix = Path(file.filename).suffix.lower()
            if suffix not in DocumentIngester.SUPPORTED_EXTENSIONS:
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_paths.append(Path(temp_file.name))

        if not temp_paths:
            raise HTTPException(
                status_code=400,
                detail="No valid files to ingest",
            )

        # Ingest all files
        total_chunks = await ingester.ingest_files(customer_id, temp_paths)

        return IngestResponse(
            customer_id=customer_id,
            chunks_created=total_chunks,
            message=f"Successfully ingested {len(temp_paths)} files",
        )
    finally:
        # Clean up temp files
        for path in temp_paths:
            path.unlink(missing_ok=True)


@router.post("/ingest-text", response_model=IngestResponse)
async def ingest_text(request: TextIngestRequest):
    """Ingest raw text into a customer's knowledge base."""
    settings = get_settings()

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    ingester = DocumentIngester(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    chunks_created = await ingester.ingest_text(
        customer_id=request.customer_id,
        text=request.text,
        source_name=request.source_name,
    )

    return IngestResponse(
        customer_id=request.customer_id,
        chunks_created=chunks_created,
        message="Successfully ingested text content",
    )


@router.delete("/{customer_id}", status_code=204)
async def delete_knowledge_base(customer_id: str):
    """Delete a customer's entire knowledge base."""
    settings = get_settings()

    ingester = DocumentIngester(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    if not ingester.has_knowledge_base(customer_id):
        raise HTTPException(
            status_code=404,
            detail="Knowledge base not found for this customer",
        )

    ingester.delete_knowledge_base(customer_id)


@router.get("/{customer_id}/status")
async def get_knowledge_base_status(customer_id: str):
    """Check if a customer has a knowledge base."""
    settings = get_settings()

    ingester = DocumentIngester(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    has_kb = ingester.has_knowledge_base(customer_id)

    return {
        "customer_id": customer_id,
        "has_knowledge_base": has_kb,
    }

