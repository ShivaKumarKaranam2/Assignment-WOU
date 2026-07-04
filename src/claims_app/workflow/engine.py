from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from claims_app.config import settings
from claims_app.models import ClaimInput, ClaimResult, ClaimState
from claims_app.services.extraction import ExtractionService
from claims_app.services.ocr import OCRService
from claims_app.services.policy import PolicyRepository
from claims_app.skills import document_validation_skill, policy_matching_skill, final_decision_skill


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
        return list(self.policy_repository.policy.get("opd_categories", {}).keys())

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
        res = document_validation_skill(state, self.ocr_service, self.policy_repository)
        return {**state, **res}

    def _policy_matching_node(self, state: ClaimState) -> ClaimState:
        res = policy_matching_skill(state, self.extraction_service, self.policy_repository)
        return {**state, **res}

    def _final_decision_node(self, state: ClaimState) -> ClaimState:
        res = final_decision_skill(state)
        return {**state, **res}


@lru_cache(maxsize=1)
def get_default_workflow() -> ClaimWorkflow:
    return ClaimWorkflow()
