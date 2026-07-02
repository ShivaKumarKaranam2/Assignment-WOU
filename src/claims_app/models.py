from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class StageName(StrEnum):
    document_validation = "document_validation"
    policy_matching = "policy_matching"
    final_decision = "final_decision"


class StageStatus(StrEnum):
    pending = "pending"
    passed = "passed"
    failed = "failed"
    warning = "warning"


class DecisionType(StrEnum):
    approved = "APPROVED"
    partial = "PARTIAL"
    rejected = "REJECTED"
    manual_review = "MANUAL_REVIEW"
    document_error = "DOCUMENT_ERROR"


class StageRecord(BaseModel):
    stage: StageName
    status: StageStatus
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class UploadedDocument(BaseModel):
    name: str
    content_type: str = "application/octet-stream"
    data: bytes = Field(repr=False)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimInput(BaseModel):
    member_id: str
    member_name: str | None = None
    treatment_type: str
    claimed_amount: float
    claim_date: date = Field(default_factory=date.today)
    provider_name: str | None = None
    notes: str | None = None
    documents: list[UploadedDocument]


class OCRDocument(BaseModel):
    file_name: str
    content_type: str
    text: str
    source: str
    quality_score: float = 0.0
    error: str | None = None
    category: str = "unknown"


class DocumentValidationResult(BaseModel):
    is_valid: bool
    message: str
    required_documents: list[str] = Field(default_factory=list)
    detected_documents: list[str] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    unreadable_documents: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    patient_name: str | None = None
    doctor_name: str | None = None
    diagnosis: str | None = None
    treatment: str | None = None
    hospital_name: str | None = None
    bill_amount: float | None = None
    bill_date: str | None = None
    prescription_present: bool | None = None
    evidence_quality: float = 0.0
    summary: str = ""
    raw_text_excerpt: str = ""
    degraded: bool = False


class PolicyCheck(BaseModel):
    rule: str
    status: StageStatus
    reason: str
    evidence: str | None = None
    confidence_impact: float = 0.0


class ClaimResult(BaseModel):
    claim_id: str
    decision: DecisionType
    approved_amount: float = 0.0
    reason: str
    confidence: float
    stage_records: list[StageRecord] = Field(default_factory=list)
    validation: DocumentValidationResult
    extraction: ExtractionResult | None = None
    policy_checks: list[PolicyCheck] = Field(default_factory=list)
    trace_reference: str
    degraded: bool = False


class AssignmentRunSummary(BaseModel):
    run_id: str
    case_id: str
    case_name: str
    status: str
    decision: str | None = None
    approved_amount: float | None = None
    confidence: float | None = None
    message: str | None = None
    trace_reference: str | None = None
    created_at: str


class AssignmentCaseResult(BaseModel):
    case_id: str
    case_name: str
    status: str
    decision: str | None = None
    approved_amount: float | None = None
    confidence: float | None = None
    message: str
    trace_reference: str
    stage_records: list[StageRecord] = Field(default_factory=list)
    raw_case: dict[str, Any] = Field(default_factory=dict)


class ClaimState(TypedDict, total=False):
    claim: ClaimInput
    claim_id: str
    validation: DocumentValidationResult
    ocr_documents: list[OCRDocument]
    extraction: ExtractionResult
    policy_checks: list[PolicyCheck]
    policy_resolution: dict[str, Any]
    decision: ClaimResult
    stage_records: list[StageRecord]
    degraded: bool
