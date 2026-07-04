from __future__ import annotations

from datetime import date

from claims_app.models import ClaimInput, DecisionType, ExtractionResult, OCRDocument, UploadedDocument
from claims_app.workflow import ClaimWorkflow


class FakePolicyRepository:
    def __init__(self, policy: dict):
        self._policy = policy

    @property
    def policy(self) -> dict:
        return self._policy

    def claim_rule(self, claim_type: str) -> dict:
        return self._policy["opd_categories"][claim_type.lower()]

    def required_documents(self, claim_type: str) -> list[str]:
        reqs = self._policy["document_requirements"].get(claim_type.upper(), {})
        return list(reqs.get("required", []))

    def document_keywords(self) -> dict[str, list[str]]:
        return {
            "hospital_bill": ["bill"],
            "discharge_summary": ["discharge"],
            "doctor_prescription": ["prescription"],
            "consultation_bill": ["consultation", "bill"],
        }

    def find_member(self, member_id: str, member_name: str | None = None) -> dict | None:
        member_id = member_id.lower()
        member_name = (member_name or "").lower()
        for member in self._policy["members"]:
            if member["member_id"].lower() == member_id or member["name"].lower() == member_name:
                return member
        return None

    @staticmethod
    def parse_date(value: str) -> date:
        return date.fromisoformat(value)


class FakeOCRService:
    def __init__(self, categories: dict[str, str]):
        self.categories = categories

    def extract_many(self, documents: list[UploadedDocument]) -> list[OCRDocument]:
        results = []
        for document in documents:
            results.append(
                OCRDocument(
                    file_name=document.name,
                    content_type=document.content_type,
                    text=f"{self.categories.get(document.name, document.name)} text",
                    source="fake",
                    quality_score=1.0,
                    category=self.categories.get(document.name, "unknown"),
                )
            )
        return results


class FakeExtractionService:
    def __init__(self, bill_amount: float | None, evidence_quality: float = 1.0, degraded: bool = False):
        self.bill_amount = bill_amount
        self.evidence_quality = evidence_quality
        self.degraded = degraded

    def extract(self, claim: dict, ocr_documents: list[OCRDocument], policy_rule: dict) -> ExtractionResult:
        return ExtractionResult(
            patient_name=claim.get("member_name"),
            doctor_name="Dr. Test",
            diagnosis="Test diagnosis",
            treatment=claim.get("treatment_type"),
            hospital_name=claim.get("provider_name"),
            bill_amount=self.bill_amount,
            bill_date=str(claim.get("claim_date")),
            prescription_present=True,
            evidence_quality=self.evidence_quality,
            summary="fake extraction",
            raw_text_excerpt="fake text",
            degraded=self.degraded,
        )


def make_policy(overrides: dict | None = None) -> dict:
    policy = {
        "opd_categories": {
            "hospitalization": {
                "coverage_limit": 50000,
                "sub_limit": 35000,
                "copay_percent": 10,
                "waiting_period_days": 30,
                "requires_pre_auth": False,
            },
            "consultation": {
                "coverage_limit": 3000,
                "sub_limit": 3000,
                "copay_percent": 0,
                "waiting_period_days": 0,
                "requires_pre_auth": False,
            },
        },
        "document_requirements": {
            "HOSPITALIZATION": {
                "required": ["hospital_bill", "discharge_summary", "doctor_prescription"],
            },
            "CONSULTATION": {
                "required": ["consultation_bill", "doctor_prescription"],
            },
        },
        "waiting_periods": {
            "initial_waiting_period_days": 30,
            "specific_conditions": {
                "diabetes": 90
            }
        },
        "exclusions": {
            "conditions": []
        },
        "coverage": {
            "per_claim_limit": 5000
        },
        "network_hospitals": ["Apollo Hospital"],
        "members": [
            {
                "member_id": "EMP001",
                "name": "Asha Patel",
                "join_date": "2025-02-01",
                "plan": "gold",
            }
        ],
    }
    if overrides:
        for key, value in overrides.items():
            policy[key] = value
    return policy


def make_claim(treatment_type: str = "consultation", claim_date: date | None = None) -> ClaimInput:
    claim_date = claim_date or date(2025, 3, 1)
    return ClaimInput(
        member_id="EMP001",
        member_name="Asha Patel",
        treatment_type=treatment_type,
        claimed_amount=1000.0,
        claim_date=claim_date,
        provider_name="Apollo Hospital",
        notes="preauth approved" if treatment_type == "hospitalization" else None,
        documents=[
            UploadedDocument(name="bill.png", content_type="image/png", data=b"bill"),
            UploadedDocument(name="prescription.png", content_type="image/png", data=b"prescription"),
            UploadedDocument(name="discharge.png", content_type="image/png", data=b"discharge"),
        ],
    )


def test_document_validation_stops_for_wrong_documents() -> None:
    workflow = ClaimWorkflow(
        policy_repository=FakePolicyRepository(make_policy()),
        ocr_service=FakeOCRService({"bill.png": "doctor_prescription", "prescription.png": "doctor_prescription", "discharge.png": "doctor_prescription"}),
        extraction_service=FakeExtractionService(bill_amount=1000.0),
    )
    result = workflow.run(make_claim(treatment_type="hospitalization"))

    assert result.decision == DecisionType.document_error
    assert "Missing required documents" in result.reason or "Uploaded document type" in result.reason
    assert result.stage_records[0].stage.value == "document_validation"
    assert result.stage_records[0].status.value == "failed"


def test_policy_rejects_when_waiting_period_is_not_met() -> None:
    workflow = ClaimWorkflow(
        policy_repository=FakePolicyRepository(make_policy()),
        ocr_service=FakeOCRService({"bill.png": "hospital_bill", "prescription.png": "doctor_prescription", "discharge.png": "discharge_summary"}),
        extraction_service=FakeExtractionService(bill_amount=1000.0),
    )
    claim = make_claim(treatment_type="hospitalization", claim_date=date(2025, 2, 5))
    result = workflow.run(claim)

    assert result.decision == DecisionType.rejected
    assert "Waiting period" in result.reason
    assert any(check.rule == "waiting_period" and check.status.value == "failed" for check in result.policy_checks)


def test_workflow_approves_when_rules_pass() -> None:
    policy = make_policy(
        {
            "opd_categories": {
                "consultation": {
                    "coverage_limit": 3000,
                    "sub_limit": 3000,
                    "copay_percent": 0,
                    "waiting_period_days": 0,
                    "requires_pre_auth": False,
                }
            }
        }
    )
    workflow = ClaimWorkflow(
        policy_repository=FakePolicyRepository(policy),
        ocr_service=FakeOCRService({"bill.png": "consultation_bill", "prescription.png": "doctor_prescription"}),
        extraction_service=FakeExtractionService(bill_amount=1000.0),
    )
    claim = make_claim(treatment_type="consultation")
    claim.documents = claim.documents[:2]
    result = workflow.run(claim)

    assert result.decision == DecisionType.approved
    assert result.approved_amount == 1000.0
    assert result.confidence >= 0.9


def test_workflow_routes_low_quality_claims_to_manual_review() -> None:
    policy = make_policy(
        {
            "opd_categories": {
                "consultation": {
                    "coverage_limit": 3000,
                    "sub_limit": 3000,
                    "copay_percent": 0,
                    "waiting_period_days": 0,
                    "requires_pre_auth": False,
                }
            }
        }
    )
    workflow = ClaimWorkflow(
        policy_repository=FakePolicyRepository(policy),
        ocr_service=FakeOCRService({"bill.png": "consultation_bill", "prescription.png": "doctor_prescription"}),
        extraction_service=FakeExtractionService(bill_amount=1000.0, evidence_quality=0.2, degraded=True),
    )
    claim = make_claim(treatment_type="consultation")
    claim.documents = claim.documents[:2]
    result = workflow.run(claim)

    assert result.decision == DecisionType.manual_review
    assert result.degraded is True
