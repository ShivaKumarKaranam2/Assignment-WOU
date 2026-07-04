from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


REQUIRED_POLICY_KEYS = {"opd_categories", "members", "document_requirements"}


def load_policy_terms(policy_file: Path) -> dict:
    if not policy_file.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_file}")
    data = json.loads(policy_file.read_text(encoding="utf-8"))
    missing = REQUIRED_POLICY_KEYS - set(data)
    if missing:
        raise ValueError(f"Policy file is missing required keys: {sorted(missing)}")
    return data


@dataclass
class PolicyRepository:
    policy_file: Path

    def __post_init__(self) -> None:
        self._policy = load_policy_terms(self.policy_file)

    @property
    def policy(self) -> dict:
        return self._policy

    def claim_rule(self, claim_type: str) -> dict:
        try:
            return self._policy["opd_categories"][claim_type.lower()]
        except KeyError as exc:
            raise KeyError(f"Unsupported claim type: {claim_type}") from exc

    def required_documents(self, claim_type: str) -> list[str]:
        try:
            # Document requirements in new policy are in uppercase
            reqs = self._policy["document_requirements"].get(claim_type.upper(), {})
            return list(reqs.get("required", []))
        except Exception:
            return []

    def document_keywords(self) -> dict[str, list[str]]:
        # Supply fallback keywords mapping standard types to search phrases
        return {
            "HOSPITAL_BILL": ["hospital bill", "inpatient bill", "hospital invoice", "bill"],
            "DISCHARGE_SUMMARY": ["discharge summary", "discharge", "summary"],
            "PRESCRIPTION": ["prescription", "rx", "doctor"],
            "PHARMACY_BILL": ["pharmacy bill", "pharmacy invoice", "medicine bill", "bill"],
            "LAB_REPORT": ["lab report", "pathology report", "test report", "lab"],
            "DENTAL_REPORT": ["dental report", "dentist report", "teeth", "dental"]
        }

    def find_member(self, member_id: str, member_name: str | None = None) -> dict | None:
        member_id = member_id.strip().lower()
        member_name = (member_name or "").strip().lower()
        for member in self._policy.get("members", []):
            if member.get("member_id", "").strip().lower() == member_id:
                return member
            if member_name and member.get("name", "").strip().lower() == member_name:
                return member
        return None

    @staticmethod
    def parse_date(value: str) -> date:
        return date.fromisoformat(value)
