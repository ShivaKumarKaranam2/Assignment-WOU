---
name: claims-final-decision
description: Use when turning validated claim evidence and policy checks into APPROVED, PARTIAL, REJECTED, MANUAL_REVIEW, or DOCUMENT_ERROR outcomes.
---

# Final Decision Skill

## Purpose

Produce the final claim outcome from the validation and policy-matching results.

## Required Outcomes

- APPROVED
- PARTIAL
- REJECTED
- MANUAL_REVIEW
- DOCUMENT_ERROR

## Required Behavior

- Return the approved amount when applicable.
- Return a clear reason.
- Return a confidence score.
- Include stage records so the UI can show what happened.
- Never crash on missing or degraded upstream data.
- Preserve the exact stage where an error occurred.

## Output

Return:

- final decision
- approved amount
- reason
- confidence
- stage trace summary

## When to Use

Use this skill only after validation and policy matching have completed.
