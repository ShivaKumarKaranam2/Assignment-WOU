# Product Requirements Document

## Product Summary

The application automates health insurance claim processing using one LangGraph agent with three stages: document validation, policy matching, and final decision.

## Goals

- Accept claims with member details, treatment type, amount, and documents
- Stop early when the wrong documents are uploaded
- Compare claims against policy terms from `policy_terms.json`
- Return a clear decision and confidence score
- Show stage-level errors in the UI
- Trace the workflow in LangSmith
- Use `uv` for project execution

## Functional Requirements

### Document Validation

The system must verify that the correct documents were uploaded for the claim type. If not, it must stop immediately and show a precise document error.

### Policy Matching

The system must compare the claim and uploaded documents against the policy rules. It must inspect waiting periods, exclusions, limits, co-pay, pre-authorization, and network constraints.

### Final Decision

The system must return one of:

- APPROVED
- PARTIAL
- REJECTED
- MANUAL_REVIEW
- DOCUMENT_ERROR

The response must include approved amount, reason, and confidence.

### Explainability

The UI must show what was checked, what passed, what failed, and why the decision was made.

### Failure Handling

If OCR, LLM, parsing, or policy evaluation fails, the system must handle the failure at that stage and show it clearly on the screen.

## Acceptance Criteria

- Wrong documents fail at stage 1 with a specific message
- Policy mismatches are visible at stage 2
- Final decisions always include reasoning and confidence
- The UI shows stage status and error state
- LangSmith traces are created for claim runs# Product Requirements Document

## Product Summary

The application automates health insurance claim processing using one LangGraph agent with three stages: document validation, policy matching, and final decision.

## Goals

- Accept claims with member details, treatment type, amount, and documents
- Stop early when the wrong documents are uploaded
- Compare claims against policy terms from `policy_terms.json`
- Return a clear decision and confidence score
- Show stage-level errors in the UI
- Trace the workflow in LangSmith
- Use `uv` for project execution

## Functional Requirements

### Document Validation

The system must verify that the correct documents were uploaded for the claim type. If not, it must stop immediately and show a precise document error.

### Policy Matching

The system must compare the claim and uploaded documents against the policy rules. It must inspect waiting periods, exclusions, limits, co-pay, pre-authorization, and network constraints.

### Final Decision

The system must return one of:

- APPROVED
- PARTIAL
- REJECTED
- MANUAL_REVIEW
- DOCUMENT_ERROR

The response must include approved amount, reason, and confidence.

### Explainability

The UI must show what was checked, what passed, what failed, and why the decision was made.

### Failure Handling

If OCR, LLM, parsing, or policy evaluation fails, the system must handle the failure at that stage and show it clearly on the screen.

## Acceptance Criteria

- Wrong documents fail at stage 1 with a specific message
- Policy mismatches are visible at stage 2
- Final decisions always include reasoning and confidence
- The UI shows stage status and error state
- LangSmith traces are created for claim runs
# Product Requirements Document
## Health Insurance Claims Processing Application

---

## 1. Product Summary

This product automates health insurance claim processing using one orchestrating agent with three stages:

1. Document Validation
2. Policy Matching
3. Final Decision

The system accepts submitted claim documents, validates whether the documents are correct, checks the claim against company policies, and returns a decision with an explanation and confidence score.

---

## 2. Problem Statement

Current claim review is manual, slow, and inconsistent. Operations teams must inspect documents, compare them against policy terms, and determine whether a claim should be approved, rejected, partially approved, or sent for manual review.

This process needs to be:
- faster
- more consistent
- explainable
- resilient to bad input
- visible to operations teams

---

## 3. Goals

- Accept claim submissions with uploaded documents.
- Validate documents before any deeper processing.
- Compare claim details against company policy terms.
- Return one of:
  - APPROVED
  - MANUAL_REVIEW
  - REJECTED
  - DOCUMENT_ERROR
- Show stage-by-stage progress and errors in the UI.
- Provide clear reasons and confidence for every outcome.
- Use LangSmith for observability.
- Use uv for project execution and dependency management.

---

## 4. Non-Goals

- Automated claim payout execution
- Fraud detection
- Full insurer back-office integration
- Complex human workflow tooling
- Multi-agent orchestration
- Free-form black-box decisions without traceability

---

## 5. Users and Personas

### Claimant / Employee
Submits claim documents and wants to know whether the claim can be processed.

### Operations Reviewer
Reviews output, sees what was checked, and understands why a claim was approved, rejected, or routed to manual review.

### Admin / Policy Owner
Maintains policy terms and expects the system to follow those rules exactly.

---

## 6. Core User Experience

### Submission Flow
1. User enters member details.
2. User selects claim type or treatment type.
3. User enters claimed amount.
4. User uploads documents.
5. System validates whether the uploaded files are correct.
6. System checks policy terms against the submitted data.
7. System returns a final decision and explanation.
8. UI shows any stage errors immediately.

### User Expectations
- Errors must be specific.
- The system must not crash.
- The user must know what to fix next.
- Manual review must be clearly indicated.
- Confidence must be visible.

---

## 7. Functional Requirements

### FR1: Claim Submission
The system must accept:
- member details
- treatment type
- claimed amount
- one or more documents

### FR2: Document Validation
The system must verify that the correct documents were uploaded for the claim type.

If documents are incorrect:
- stop processing immediately
- return DOCUMENT_ERROR
- show a clear message explaining what is wrong and what is required

### FR3: Policy Matching
The system must compare the submission and uploaded documents against policy terms from `policy_terms.json`.

The system must check:
- coverage rules
- waiting periods
- exclusions
- sub-limits
- co-pay rules
- pre-authorization requirements
- network rules
- member eligibility

### FR4: Final Decision
The system must return one of:
- APPROVED
- MANUAL_REVIEW
- REJECTED
- DOCUMENT_ERROR

The response must include:
- approved amount
- reason
- confidence score

### FR5: Explainability
For each claim, the system must show:
- what was checked
- what passed
- what failed
- why the final decision was made

### FR6: Failure Handling
If a component fails:
- the system must not crash
- the failure must be isolated to the stage where it occurred
- the UI must show the failure clearly
- confidence must be lowered when evidence quality is poor

### FR7: Observability
The system must send traces to LangSmith so operations can inspect:
- stage inputs
- stage outputs
- rule checks
- failures
- fallbacks
- confidence effects

---

## 8. Decision Rules

### APPROVED
Use when:
- documents are correct
- policy checks pass
- claimed amount is fully covered
- confidence is sufficient

### PARTIAL
Use when:
- part of the claim is covered
- sub-limits or co-pay rules reduce the payable amount

### REJECTED
Use when:
- policy explicitly denies the claim
- waiting period has not been satisfied
- excluded treatment is submitted
- required pre-authorization is missing

### MANUAL_REVIEW
Use when:
- evidence is incomplete
- documents are partly unreadable
- policy outcome is uncertain
- confidence is too low for automatic handling

### DOCUMENT_ERROR
Use when:
- uploaded document type is wrong
- required document is missing
- input files are unusable for processing

---

## 9. Error Handling Requirements

### Stage 1 Errors
Document validation failures must be returned immediately and shown to the user.

### Stage 2 Errors
Policy matching failures must return a policy-specific result or manual review, with the exact failed policy checks shown.

### Stage 3 Errors
Decision generation errors must fail safely, preserve traceability, and avoid crashing the application.

---

## 10. Data and Policy Requirements

### Data Source of Truth
The application must use `policy_terms.json` as the source of policy logic.

### Data Expected
- coverage categories
- limits
- sub-limits
- co-pay rules
- waiting periods
- exclusions
- pre-authorization requirements
- network rules
- member roster

### Requirement
Policy behavior must not be hardcoded into code paths. It must come from the policy file.

---

## 11. UI Requirements

The UI must:
- be simple and user-friendly
- show stage progress
- display validation failures clearly
- show policy checks clearly
- show the final outcome clearly
- show confidence
- show trace details or a trace reference

The UI should help the user answer:
- What happened?
- What failed?
- What do I need to do next?

---

## 12. Success Metrics

- Claims with wrong documents are rejected at stage 1 with a specific message.
- Policy mismatches are explained clearly at stage 2.
- Final outcomes are returned with a valid confidence score.
- Operations users can understand every decision.
- The application handles failures without crashing.
- LangSmith traces are available for review.

---

## 13. Acceptance Criteria

A claim is acceptable if all of the following are true:
- it accepts claim details and documents
- it validates document correctness before processing
- it checks policy terms against uploaded evidence
- it returns one of the required decision states
- it shows the reason and confidence
- it handles errors at the stage where they occur
- it displays the result in the UI
- it writes traces to LangSmith

---

## 14. Constraints

- Must use uv
- Must use a single agent
- Must have three stages only
- Must expose stage-level errors in the UI
- Must remain explainable
- Must not hardcode policy logic
- Must degrade gracefully on failures

---

## 15. Risks

- Poor-quality documents may reduce confidence significantly.
- Ambiguous policy rules may increase manual review rates.
- OCR or parsing failures may limit extraction quality.
- Missing or incomplete policy data may affect decision accuracy.

---

## 16. Open Questions

- Which OCR provider should be used first?
- Which language model should support extraction and explanation?
- Should manual review be only a UI state or also a persisted workflow state?
- Should traces be stored locally, in LangSmith only, or both?