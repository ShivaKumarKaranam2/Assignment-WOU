---
name: claims-processing
description: Use when processing health insurance claims, orchestrating the three stage skills in order, and ensuring stage-level errors appear in the UI.
---

# Claims Processing Orchestrator Skill

## Purpose

Use this skill to coordinate the three stage-specific claims skills in order:

1. Document validation
2. Policy matching
3. Final decision

This orchestrator must stop at the exact stage where an error occurs and surface that error clearly to the user.

## Required Flow

### Stage 1

Use [Document Validation Skill](document-validation/SKILL.md) first.

### Stage 2

If stage 1 passes, use [Policy Matching Skill](policy-matching/SKILL.md).

### Stage 3

If stage 2 completes, use [Final Decision Skill](final-decision/SKILL.md).

## Required Behavior

- Keep the workflow strictly stage-based.
- Stop immediately when a stage produces a hard error.
- Keep the error visible in the UI.
- Preserve the stage trace and confidence impact.
- Use the policy file as the source of truth for stage 2.

## Explainability Requirements

Every run must show:

- what was checked
- what passed
- what failed
- why the final decision was made
- which stage caused any failure

## Observability Requirements

If LangSmith is configured, capture trace data for each stage.

Required trace metadata:

- claim ID
- member ID
- claim type
- validation status
- policy checks
- extraction quality
- final decision
- confidence
- degraded-state flags

## Error Handling Rules

- Stage 1 errors must stop the workflow immediately.
- Stage 2 errors must either reject, partial-approve, or route to manual review with an explicit reason.
- Stage 3 errors must never crash the application.
- The UI must show the error at the stage where it happened.

## When to Use

Use this skill whenever the task involves claim intake, document checks, policy comparison, explanation generation, confidence scoring, or review-screen rendering.
