from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from claims_app.config import settings
from claims_app.case_runner import run_cases
from claims_app.db import get_run, init_db, list_runs, save_live_result
from claims_app.models import ClaimInput, ClaimResult, UploadedDocument
from claims_app.observability import configure_observability, langsmith_status
from claims_app.workflow import get_default_workflow


configure_observability()
init_db()


app = FastAPI(title="Claims Agentic Health API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STORE: dict[str, ClaimResult] = {}


@app.get("/health")
def health() -> dict[str, str]:
    status = {"status": "ok"}
    status.update({f"langsmith_{key}": value for key, value in langsmith_status().items()})
    return status


@app.get("/claims/{claim_id}", response_model=ClaimResult)
def get_claim(claim_id: str) -> ClaimResult:
    result = _STORE.get(claim_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return result


@app.post("/claims/submit", response_model=ClaimResult)
async def submit_claim(
    member_id: Annotated[str, Form(...)],
    treatment_type: Annotated[str, Form(...)],
    claimed_amount: Annotated[float, Form(...)],
    claim_date: Annotated[date, Form(...)],
    documents: Annotated[list[UploadFile], File(...)],
    member_name: Annotated[str | None, Form()] = None,
    provider_name: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
) -> ClaimResult:
    if not documents:
        raise HTTPException(status_code=400, detail="At least one document is required")

    uploaded_documents: list[UploadedDocument] = []
    for document in documents:
        data = await document.read()
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail=f"File too large: {document.filename}")
        uploaded_documents.append(
            UploadedDocument(
                name=document.filename or "uploaded_document",
                content_type=document.content_type or "application/octet-stream",
                data=data,
            )
        )

    claim = ClaimInput(
        member_id=member_id,
        member_name=member_name,
        treatment_type=treatment_type,
        claimed_amount=claimed_amount,
        claim_date=claim_date,
        provider_name=provider_name,
        notes=notes,
        documents=uploaded_documents,
    )
    from langchain_core.tracers.context import tracing_v2_enabled

    with tracing_v2_enabled(project_name=settings.langchain_project or "claims-agentic-health"):
        result = get_default_workflow().run(claim)
    _STORE[result.claim_id] = result
    save_live_result(result)
    return result


@app.get("/claims/{claim_id}/trace")
def get_trace(claim_id: str) -> dict:
    result = _STORE.get(claim_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {
        "claim_id": result.claim_id,
        "trace_reference": result.trace_reference,
        "stage_records": [record.model_dump() for record in result.stage_records],
        "decision": result.decision,
        "validation": result.validation,
        "policy_checks": [check.model_dump() for check in result.policy_checks],
        "extraction": result.extraction.model_dump() if result.extraction else None,
    }


@app.get("/runs")
def get_runs(limit: int = 100) -> list[dict]:
    return list_runs(limit=limit)


@app.get("/runs/{run_id}")
def get_run_details(run_id: str) -> dict:
    result = get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@app.post("/assignment/run")
def run_assignment(payload: dict) -> dict:
    test_cases = payload.get("test_cases", [])
    results = run_cases(test_cases)
    return {
        "total_cases": len(results),
        "results": [result.model_dump() for result in results],
    }


def run() -> None:
    import uvicorn

    uvicorn.run("claims_app.api:app", host="0.0.0.0", port=8000, reload=True)
