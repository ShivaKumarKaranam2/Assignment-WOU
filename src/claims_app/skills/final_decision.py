from __future__ import annotations

from claims_app.models import ClaimResult, ClaimState, DecisionType, StageName, StageRecord, StageStatus

def _append_record(records: list[StageRecord], record: StageRecord) -> list[StageRecord]:
    updated = list(records)
    updated.append(record)
    return updated

def final_decision_skill(state: ClaimState) -> dict:
    if state.get("decision"):
        return {"decision": state["decision"]}

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
        return {"decision": decision}

    resolution = state.get("policy_resolution") or {
        "decision": DecisionType.manual_review,
        "approved_amount": 0.0,
        "reason": "No policy resolution was produced.",
        "confidence": 0.35,
    }
    
    status = StageStatus.passed if resolution["decision"] != DecisionType.rejected else StageStatus.failed
    if resolution["decision"] == DecisionType.manual_review:
        status = StageStatus.warning
        
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
                status=status,
                message=resolution["reason"],
                details={
                    "approved_amount": resolution["approved_amount"],
                    "decision": resolution["decision"].value if hasattr(resolution["decision"], "value") else str(resolution["decision"]),
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
    return {"decision": decision}
