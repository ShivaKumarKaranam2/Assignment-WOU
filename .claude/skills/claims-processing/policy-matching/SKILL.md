---
name: claims-policy-matching
description: Use when comparing validated claim details and uploaded documents against company policy terms, limits, exclusions, and eligibility rules.
---

# Policy Matching Skill

## Purpose

Compare a validated claim against policy terms in `data/policy_terms.json`.

## What to Check

- Member eligibility
- Waiting periods
- Exclusions
- Coverage limits
- Sub-limits
- Co-pay rules
- Pre-authorization requirements
- Network restrictions
- Evidence quality and completeness

## Required Behavior

- Use the JSON policy file as the source of truth.
- Record every passed, failed, and uncertain check.
- Lower confidence when the documents are partially unreadable or incomplete.
- Escalate to manual review when the evidence is not strong enough for a confident automatic decision.
- Do not make a final decision yet unless the workflow is explicitly short-circuiting on a hard policy rejection.

## Output

Return:

- policy checks
- confidence impact
- manual review signals
- any rule-based rejection reason

## When to Use

Use this skill only after document validation has passed.
