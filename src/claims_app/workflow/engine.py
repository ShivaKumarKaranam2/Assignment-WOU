from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from claims_app.config import settings
from claims_app.models import (
    ClaimInput,
    ClaimResult,
    ClaimState,
    DecisionType,
    DocumentValidationResult,
    ExtractionResult,
    OCRDocument,
    PolicyCheck,
    StageName,
    StageRecord,
    StageStatus,
)
from claims_app.services.extraction import ExtractionService
from claims_app.services.ocr import OCRService
from claims_app.services.policy import PolicyRepository


def _append_record(records: list[StageRecord], record: StageRecord) -> list[StageRecord]:
    updated = list(records)
    updated.append(record)
    return updated


def _member_names(member: dict | None) -> set[str]:
    if not member:
        return set()
    return {str(member.get("name", "")).strip().lower(), str(member.get("member_id", "")).strip().lower()}


@dataclass
class ClaimWorkflow:
    policy_repository: PolicyRepository | None = None
    ocr_service: OCRService | None = None
    extraction_service: ExtractionService | None = None
    _graph: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.policy_repository = self.policy_repository or PolicyRepository(settings.policy_file)
        self.ocr_service = self.ocr_service or OCRService(self.policy_repository)
        self.extraction_service = self.extraction_service or ExtractionService()
        self._graph = self._build_graph()

    @property
    def claim_types(self) -> list[str]:
        return list(self.policy_repository.policy.get("claim_types", {}).keys())

    def run(self, claim: ClaimInput) -> ClaimResult:
        claim_id = str(uuid4())
        initial_state: ClaimState = {
            "claim": claim,
            "claim_id": claim_id,
            "stage_records": [],
            "degraded": False,
        }
        final_state = self._graph.invoke(
            initial_state,
            config={
                "run_name": "claims_processing_workflow",
                "metadata": {
                    "claim_id": claim_id,
                    "member_id": claim.member_id,
                    "claim_type": claim.treatment_type,
                },
            },
        )
        return final_state["decision"]

    def _build_graph(self):
        graph = StateGraph(ClaimState)
        graph.add_node("document_validation", self._document_validation_node)
        graph.add_node("policy_matching", self._policy_matching_node)
        graph.add_node("final_decision", self._final_decision_node)
        graph.add_edge(START, "document_validation")
        graph.add_conditional_edges(
            "document_validation",
            self._after_validation,
            {
                "policy_matching": "policy_matching",
                "final_decision": "final_decision",
            },
        )
        graph.add_edge("policy_matching", "final_decision")
        graph.add_edge("final_decision", END)
        return graph.compile()

    def _after_validation(self, state: ClaimState) -> str:
        validation = state["validation"]
        return "final_decision" if not validation.is_valid else "policy_matching"

    def _document_validation_node(self, state: ClaimState) -> ClaimState:
        claim = state["claim"]
        try:
            required_documents = self.policy_repository.required_documents(claim.treatment_type)
        except KeyError:
            required_documents = []
            validation = DocumentValidationResult(
                is_valid=False,
                message=f"Unsupported claim type '{claim.treatment_type}'. Please choose a supported treatment type.",
                required_documents=[],
                detected_documents=[],
                missing_documents=[],
                unreadable_documents=[],
            )
            stage_records = _append_record(
                state.get("stage_records", []),
                StageRecord(
                    stage=StageName.document_validation,
                    status=StageStatus.failed,
                    message=validation.message,
                    details={"claim_type": claim.treatment_type},
                ),
            )
            return {**state, "validation": validation, "ocr_documents": [], "stage_records": stage_records, "degraded": True}

        ocr_documents = self.ocr_service.extract_many(claim.documents)
        detected_documents = [document.category for document in ocr_documents if document.category != "unknown"]
        unreadable_documents = [document.file_name for document in ocr_documents if document.error or not document.text.strip()]
        missing_documents = [required for required in required_documents if required not in detected_documents]

        is_valid = not missing_documents and not unreadable_documents and bool(claim.documents)
        if is_valid:
            message = "Document validation passed."
            status = StageStatus.passed
        else:
            if not claim.documents:
                message = "No documents were uploaded. Please upload the required claim documents."
            elif missing_documents and unreadable_documents:
                message = (
                    f"Missing required documents ({', '.join(missing_documents)}) and at least one file could not be read ({', '.join(unreadable_documents)}). "
                    "Please upload the exact required documents as clear image or PDF files."
                )
            elif missing_documents:
                message = (
                    f"Missing required documents for {claim.treatment_type}: {', '.join(missing_documents)}. "
                    "Please upload the exact required document(s)."
                )
            else:
                message = (
                    f"Uploaded files could not be read clearly: {', '.join(unreadable_documents)}. "
                    "Please upload a clearer image or PDF."
                )
            status = StageStatus.failed

        validation = DocumentValidationResult(
            is_valid=is_valid,
            message=message,
            required_documents=required_documents,
            detected_documents=detected_documents,
            missing_documents=missing_documents,
            unreadable_documents=unreadable_documents,
        )
        stage_records = _append_record(
            state.get("stage_records", []),
            StageRecord(
                stage=StageName.document_validation,
                status=status,
                message=message,
                details={
                    "required_documents": required_documents,
                    "detected_documents": detected_documents,
                    "missing_documents": missing_documents,
                    "unreadable_documents": unreadable_documents,
                },
            ),
        )
        return {
            **state,
            "validation": validation,
            "ocr_documents": ocr_documents,
            "stage_records": stage_records,
            "degraded": state.get("degraded", False) or any(document.error for document in ocr_documents),
        }

    def _policy_matching_node(self, state: ClaimState) -> ClaimState:
        claim = state["claim"]
        policy_checks: list[PolicyCheck] = []
        stage_records = list(state.get("stage_records", []))
        try:
            policy_rule = self.policy_repository.claim_rule(claim.treatment_type)
        except KeyError as exc:
            policy_checks.append(
                PolicyCheck(
                    rule="claim_type",
                    status=StageStatus.failed,
                    reason=str(exc),
                    evidence=claim.treatment_type,
                    confidence_impact=0.25,
                )
            )
            resolution = {
                "decision": DecisionType.rejected,
                "approved_amount": 0.0,
                "reason": f"Unsupported claim type: {claim.treatment_type}",
                "confidence": 0.45,
            }
            stage_records.append(
                StageRecord(
                    stage=StageName.policy_matching,
                    status=StageStatus.failed,
                    message=f"Unsupported claim type: {claim.treatment_type}",
                    details={"policy_checks": [check.model_dump() for check in policy_checks]},
                )
            )
            return {**state, "policy_checks": policy_checks, "policy_resolution": resolution, "stage_records": stage_records, "degraded": True}

        extraction = self.extraction_service.extract(claim.model_dump(mode="python"), state.get("ocr_documents", []), policy_rule)
        member = self.policy_repository.find_member(claim.member_id, claim.member_name)

        if member is None:
            policy_checks.append(
                PolicyCheck(
                    rule="member_lookup",
                    status=StageStatus.failed,
                    reason="Member not found in the policy roster.",
                    evidence=claim.member_id,
                    confidence_impact=0.4,
                )
            )
            resolution = {
                "decision": DecisionType.rejected,
                "approved_amount": 0.0,
                "reason": "Member not found in policy roster.",
                "confidence": 0.4,
            }
        else:
            resolution = self._evaluate_policy(claim, policy_rule, member, extraction, policy_checks)

        degraded = state.get("degraded", False) or extraction.degraded or extraction.evidence_quality < 0.45
        if resolution["decision"] == DecisionType.manual_review:
            stage_status = StageStatus.warning
        elif resolution["decision"] in {DecisionType.rejected, DecisionType.document_error}:
            stage_status = StageStatus.failed
        else:
            stage_status = StageStatus.warning if degraded else StageStatus.passed
        stage_records.append(
            StageRecord(
                stage=StageName.policy_matching,
                status=stage_status,
                message=resolution["reason"],
                details={
                    "policy_checks": [check.model_dump() for check in policy_checks],
                    "extraction": extraction.model_dump(),
                    "decision_hint": resolution,
                },
            )
        )
        return {
            **state,
            "extraction": extraction,
            "policy_checks": policy_checks,
            "policy_resolution": resolution,
            "stage_records": stage_records,
            "degraded": degraded,
        }

    def _evaluate_policy(
        self,
        claim: ClaimInput,
        policy_rule: dict,
        member: dict,
        extraction: ExtractionResult,
        policy_checks: list[PolicyCheck],
    ) -> dict:
        hard_reject = False
        manual_review = False
        reasons: list[str] = []
        confidence = 0.95

        coverage_start = self.policy_repository.parse_date(str(member.get("coverage_start_date")))
        active_days = (claim.claim_date - coverage_start).days
        waiting_period_days = int(policy_rule.get("waiting_period_days", 0))
        if active_days < waiting_period_days:
            hard_reject = True
            reason = f"Waiting period not completed. Policy requires {waiting_period_days} days and only {active_days} days have elapsed."
            reasons.append(reason)
            policy_checks.append(
                PolicyCheck(
                    rule="waiting_period",
                    status=StageStatus.failed,
                    reason=reason,
                    evidence=f"coverage_start_date={coverage_start.isoformat()} claim_date={claim.claim_date.isoformat()}",
                    confidence_impact=0.35,
                )
            )
            confidence -= 0.35
        else:
            policy_checks.append(
                PolicyCheck(
                    rule="waiting_period",
                    status=StageStatus.passed,
                    reason="Waiting period satisfied.",
                    evidence=f"{active_days} days active",
                    confidence_impact=0.0,
                )
            )

        if policy_rule.get("preauth_required", False):
            preauth_present = bool(claim.notes and "preauth" in claim.notes.lower())
            if preauth_present:
                policy_checks.append(
                    PolicyCheck(
                        rule="pre_authorization",
                        status=StageStatus.passed,
                        reason="Pre-authorization evidence was found in the claim notes.",
                        evidence=claim.notes,
                        confidence_impact=0.0,
                    )
                )
            else:
                manual_review = True
                reason = "Pre-authorization is required but was not explicitly confirmed in the uploaded materials."
                reasons.append(reason)
                policy_checks.append(
                    PolicyCheck(
                        rule="pre_authorization",
                        status=StageStatus.warning,
                        reason=reason,
                        evidence=claim.notes or "not provided",
                        confidence_impact=0.2,
                    )
                )
                confidence -= 0.2

        if policy_rule.get("network_required", False):
            provider_name = (claim.provider_name or "").strip().lower()
            allowed_network = {str(item).strip().lower() for item in member.get("network_hospitals", [])}
            if provider_name and provider_name in allowed_network:
                policy_checks.append(
                    PolicyCheck(
                        rule="network",
                        status=StageStatus.passed,
                        reason="Provider is in network.",
                        evidence=claim.provider_name,
                    )
                )
            else:
                hard_reject = True
                reason = "Provider is not in the required network for this claim type."
                reasons.append(reason)
                policy_checks.append(
                    PolicyCheck(
                        rule="network",
                        status=StageStatus.failed,
                        reason=reason,
                        evidence=claim.provider_name or "not provided",
                        confidence_impact=0.3,
                    )
                )
                confidence -= 0.3

        if extraction.degraded or extraction.evidence_quality < 0.45:
            manual_review = True
            reason = "Document quality is low or extraction was degraded."
            reasons.append(reason)
            policy_checks.append(
                PolicyCheck(
                    rule="evidence_quality",
                    status=StageStatus.warning,
                    reason=reason,
                    evidence=f"quality={extraction.evidence_quality}",
                    confidence_impact=0.15,
                )
            )
            confidence -= 0.15

        if extraction.bill_amount is None:
            manual_review = True
            reason = "Bill amount could not be extracted reliably from the documents."
            reasons.append(reason)
            policy_checks.append(
                PolicyCheck(
                    rule="bill_amount",
                    status=StageStatus.warning,
                    reason=reason,
                    evidence=extraction.raw_text_excerpt[:200],
                    confidence_impact=0.1,
                )
            )
            confidence -= 0.1

        coverage_limit = float(policy_rule.get("coverage_limit", claim.claimed_amount))
        sub_limit = float(policy_rule.get("sub_limit", coverage_limit))
        co_pay_rate = float(policy_rule.get("co_pay_rate", 0.0))
        eligible_amount = min(claim.claimed_amount, coverage_limit, sub_limit)
        approved_amount = round(max(0.0, eligible_amount * (1 - co_pay_rate)), 2)

        if hard_reject:
            decision = DecisionType.rejected
            approved_amount = 0.0
        elif manual_review:
            decision = DecisionType.manual_review
        elif approved_amount < claim.claimed_amount:
            decision = DecisionType.partial
        else:
            decision = DecisionType.approved

        if decision == DecisionType.partial:
            reasons.append("The claim is covered but reduced by policy limits or co-pay.")
        elif decision == DecisionType.approved:
            reasons.append("The claim satisfies policy checks and is fully covered.")
        elif decision == DecisionType.manual_review and not reasons:
            reasons.append("The claim requires human review because evidence is incomplete or uncertain.")
        elif decision == DecisionType.rejected and not reasons:
            reasons.append("The claim does not satisfy a required policy rule.")

        confidence = max(0.1, min(confidence, 0.99))
        return {
            "decision": decision,
            "approved_amount": approved_amount,
            "reason": " ".join(reasons),
            "confidence": round(confidence, 2),
        }

    def _final_decision_node(self, state: ClaimState) -> ClaimState:
        if state.get("decision"):
            return state

        claim = state["claim"]
        validation = state["validation"]
        stage_records = list(state.get("stage_records", []))

        if not validation.is_valid:
            decision = ClaimResult(
                claim_id=state["claim_id"],
                decision=DecisionType.document_error,
                approved_amount=0.0,
                reason=validation.message,
                confidence=0.98 if validation.missing_documents else 0.9,
                stage_records=_append_record(
                    stage_records,
                    StageRecord(
                        stage=StageName.final_decision,
                        status=StageStatus.failed,
                        message=validation.message,
                        details={"validation": validation.model_dump()},
                    ),
                ),
                validation=validation,
                extraction=state.get("extraction"),
                policy_checks=state.get("policy_checks", []),
                trace_reference=state["claim_id"],
                degraded=True,
            )
            return {**state, "decision": decision}

        resolution = state.get("policy_resolution") or {
            "decision": DecisionType.manual_review,
            "approved_amount": 0.0,
            "reason": "No policy resolution was produced.",
            "confidence": 0.35,
        }
        decision = ClaimResult(
            claim_id=state["claim_id"],
            decision=resolution["decision"],
            approved_amount=resolution["approved_amount"],
            reason=resolution["reason"],
            confidence=resolution["confidence"],
            stage_records=_append_record(
                stage_records,
                StageRecord(
                    stage=StageName.final_decision,
                    status=StageStatus.passed if resolution["decision"] != DecisionType.rejected else StageStatus.failed,
                    message=resolution["reason"],
                    details={
                        "approved_amount": resolution["approved_amount"],
                        "decision": resolution["decision"],
                        "claim_type": claim.treatment_type,
                    },
                ),
            ),
            validation=validation,
            extraction=state.get("extraction"),
            policy_checks=state.get("policy_checks", []),
            trace_reference=state["claim_id"],
            degraded=state.get("degraded", False) or (state.get("extraction") and state["extraction"].degraded),
        )
        return {**state, "decision": decision}


@lru_cache(maxsize=1)
def get_default_workflow() -> ClaimWorkflow:
    return ClaimWorkflow()
