from __future__ import annotations

import json

import pytest

from claims_app.services.policy import load_policy_terms


def test_policy_loader_requires_core_keys(tmp_path) -> None:
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({"claim_types": {}, "members": []}), encoding="utf-8")

    with pytest.raises(ValueError):
        load_policy_terms(policy_file)

