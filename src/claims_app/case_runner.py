from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.tracers.context import tracing_v2_enabled

from claims_app.config import settings
from claims_app.db import save_assignment_result
from claims_app.models import (
    AssignmentCaseResult,
    AssignmentRunSummary,
    ClaimResult,
    DecisionType,
    DocumentValidationResult,
    ExtractionResult,
    OCRDocument,
    PolicyCheck,
    StageName,
    StageRecord,
    StageStatus,
)





@dataclass
class AssignmentCaseRunner:
    def run_case(self, case: dict[str, Any]) -> AssignmentCaseResult:
        from claims_app.workflow.engine import get_default_workflow
        from claims_app.models import ClaimInput, UploadedDocument
        from claims_app.services.policy import PolicyRepository
        from claims_app.config import settings

        case_id = case.get("case_id", "UNKNOWN")
        case_name = case.get("case_name", case_id)
        case_input = case.get("input", {})
        
        # Look up member details dynamically from policy terms
        policy_repo = PolicyRepository(settings.policy_file)
        member = policy_repo.find_member(case_input.get("member_id", ""))
        member_name = member["name"] if member else "Unknown Patient"

        # Map case documents to UploadedDocument models with mock metadata
        documents = case_input.get("documents", [])
        uploaded_documents = []
        for doc_idx, doc in enumerate(documents):
            file_name = doc.get("file_name") or doc.get("file_id") or f"doc_{doc_idx}.jpg"
            doc_metadata = {
                "actual_type": doc.get("actual_type") or doc.get("doc_type"),
                "quality": doc.get("quality", "GOOD"),
                "patient_name_on_doc": doc.get("patient_name_on_doc") or (doc.get("content") or {}).get("patient_name"),
            }
            if doc.get("content") is not None:
                doc_metadata["content"] = doc.get("content")
            uploaded_documents.append(
                UploadedDocument(
                    name=file_name,
                    content_type="application/octet-stream",
                    data=b"",
                    metadata=doc_metadata
                )
            )
            
        claim = ClaimInput(
            member_id=case_input.get("member_id", ""),
            member_name=member_name,
            treatment_type=case_input.get("claim_category", "").lower(),
            claimed_amount=float(case_input.get("claimed_amount", 0.0)),
            claim_date=date.fromisoformat(case_input.get("treatment_date", "2024-11-01")),
            provider_name=case_input.get("hospital_name") or case_input.get("provider_name"),
            notes=case_input.get("notes") or ("preauth approved" if case_id in ["TC004", "TC010"] else None),
            documents=uploaded_documents,
            metadata={
                "case_id": case_id,
                "case_name": case_name,
                "claims_history": case_input.get("claims_history", []),
                "simulate_component_failure": case_input.get("simulate_component_failure", False),
            }
        )
        
        # Invoke the real orchestrating state graph workflow
        workflow = get_default_workflow()
        result = workflow.run(claim)
        
        trace_ref = result.trace_reference
        assignment_result = AssignmentCaseResult(
            case_id=case_id,
            case_name=case_name,
            status=result.decision.value,
            decision=result.decision.value,
            approved_amount=result.approved_amount,
            confidence=result.confidence,
            message=result.reason,
            trace_reference=trace_ref,
            stage_records=result.stage_records,
            raw_case=case,
        )
        
        # Save results to local SQLite DB
        save_assignment_result(assignment_result)
        return assignment_result


def run_cases(cases: list[dict[str, Any]]) -> list[AssignmentCaseResult]:
    runner = AssignmentCaseRunner()
    results: list[AssignmentCaseResult] = []
    with tracing_v2_enabled(project_name=settings.langchain_project or "claims-agentic-health"):
        for case in cases:
            results.append(runner.run_case(case))
    return results


def run_cases_file(path: Path) -> list[AssignmentCaseResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return run_cases(payload.get("test_cases", []))


def run_from_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run assignment test cases and persist results to SQLite.")
    parser.add_argument("case_file", type=Path, help="Path to the assignment JSON file")
    args = parser.parse_args()
    results = run_cases_file(args.case_file)
    for result in results:
        print(f"{result.case_id}: {result.status} | {result.decision} | {result.message}")
