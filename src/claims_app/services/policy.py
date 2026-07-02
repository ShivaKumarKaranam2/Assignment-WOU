from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


REQUIRED_POLICY_KEYS = {"claim_types", "members", "document_keywords"}


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
            return self._policy["claim_types"][claim_type]
        except KeyError as exc:
            raise KeyError(f"Unsupported claim type: {claim_type}") from exc

    def required_documents(self, claim_type: str) -> list[str]:
        return list(self.claim_rule(claim_type).get("required_documents", []))

    def document_keywords(self) -> dict[str, list[str]]:
        return {name: list(keywords) for name, keywords in self._policy.get("document_keywords", {}).items()}

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
