# Eval Report

## Scope

This report covers the 12 assignment cases in `data/assignment_test_cases.json`. The results below use the latest corrected run stored in SQLite.

## Summary

- Total cases: 12
- Matched expected outcome: 12
- Mismatched outcome: 0
- Runtime failures: 0

The first run exposed a document-type normalization bug in TC001, but that was corrected before the final run. The report below reflects the corrected results.

## Results

### TC001 - Wrong Document Uploaded
Expected: stop before decision and name the uploaded document type and the required types.

Actual decision: `DOCUMENT_ERROR`

Trace:
- `document_validation: failed`
- Uploaded document type PRESCRIPTION was provided, but CONSULTATION requires PRESCRIPTION, HOSPITAL_BILL.

Match: Yes

Why it matched:
- The workflow stopped at document validation.
- The message named both the uploaded type and the required types.

### TC002 - Unreadable Document
Expected: identify unreadable pharmacy bill and ask for re-upload.

Actual decision: `DOCUMENT_ERROR`

Trace:
- `document_validation: failed`
- The pharmacy_bill document cannot be read clearly. Please re-upload that specific document.

Match: Yes

Why it matched:
- The unreadable document was isolated to the pharmacy bill.
- The claim did not proceed to rejection.

### TC003 - Documents Belong to Different Patients
Expected: detect patient mismatch and surface the names.

Actual decision: `DOCUMENT_ERROR`

Trace:
- `document_validation: failed`
- Documents belong to different patients: Arjun Mehta, Rajesh Kumar. Please upload matching documents for one patient.

Match: Yes

Why it matched:
- The validation stage detected the mismatch.
- The output named the patients found on the documents.

### TC004 - Clean Consultation — Full Approval
Expected: approve `₹1,350` with 10% co-pay.

Actual decision: `APPROVED`

Approved amount: `1350.0`

Trace:
- `final_decision: passed`
- Clean consultation approved after 10% co-pay. Final approved amount ₹1350.

Match: Yes

Why it matched:
- The claim was valid, covered, and within policy limits.
- The 10% co-pay was applied correctly.

### TC005 - Waiting Period — Diabetes
Expected: reject for waiting period and state eligibility date.

Actual decision: `REJECTED`

Trace:
- `policy_matching: failed`
- Waiting period applies. Member becomes eligible for diabetes-related claims on 2024-11-30.

Match: Yes

Why it matched:
- The claim fell inside the 90-day waiting period.
- The output included the future eligibility date.

### TC006 - Dental Partial Approval — Cosmetic Exclusion
Expected: partially approve only the covered root canal line item.

Actual decision: `PARTIAL`

Approved amount: `8000.0`

Trace:
- `policy_matching: warning`
- Root canal treatment is covered, but teeth whitening is cosmetic and excluded.

Match: Yes

Why it matched:
- The covered item was approved.
- The cosmetic item was excluded.

### TC007 - MRI Without Pre-Authorization
Expected: reject for missing pre-auth and explain resubmission.

Actual decision: `REJECTED`

Trace:
- `policy_matching: failed`
- Pre-authorization was required for MRI above ₹10,000 and was not obtained. Please resubmit with pre-auth approval.

Match: Yes

Why it matched:
- The system rejected the claim because pre-auth was missing.
- The message told the member how to resubmit.

### TC008 - Per-Claim Limit Exceeded
Expected: reject because ₹7,500 exceeds the ₹5,000 limit.

Actual decision: `REJECTED`

Trace:
- `policy_matching: failed`
- Claimed amount ₹7,500 exceeds the per-claim limit of ₹5,000.

Match: Yes

Why it matched:
- The claim exceeded the configured per-claim limit.
- The message clearly named both the claim amount and the limit.

### TC009 - Fraud Signal — Multiple Same-Day Claims
Expected: manual review with specific signals.

Actual decision: `MANUAL_REVIEW`

Trace:
- `policy_matching: warning`
- Unusual same-day claim pattern detected: CLM_0081 on 2024-10-30, CLM_0082 on 2024-10-30, CLM_0083 on 2024-10-30. Routed to manual review.

Match: Yes

Why it matched:
- The system did not auto-reject a suspicious pattern.
- It flagged the claims history as the trigger.

### TC010 - Network Hospital — Discount Applied
Expected: approve `₹3,240` after network discount then co-pay.

Actual decision: `APPROVED`

Approved amount: `3240.0`

Trace:
- `policy_matching: passed`
- Network discount applied before co-pay. Gross ₹4500, discount ₹900, co-pay ₹360, final ₹3240.

Match: Yes

Why it matched:
- The calculation order was correct.
- The final amount matched the expected amount exactly.

### TC011 - Component Failure — Graceful Degradation
Expected: approve with lower confidence and visible failure note.

Actual decision: `APPROVED`

Approved amount: `4000.0`

Trace:
- `policy_matching: warning`
- A component failed mid-processing and was skipped. Confidence reduced; manual review recommended.
- `policy_matching: warning`
- A downstream component failed and was skipped, but the workflow continued.

Match: Yes

Why it matched:
- The pipeline did not crash.
- The output showed the failure and reduced confidence.
- The note recommended manual review.

### TC012 - Excluded Treatment
Expected: reject for excluded treatment with high confidence.

Actual decision: `REJECTED`

Trace:
- `policy_matching: failed`
- Bariatric consultation and diet program are excluded treatments under the policy.

Match: Yes

Why it matched:
- The claim hit an explicit exclusion.
- The confidence remained high because the rule was clear.

## Conclusion

The current implementation satisfied all 12 assignment cases in the final corrected run. The main thing verified by this report is not only the decision label, but also the quality of the user-facing explanation and the stage at which the workflow stopped or degraded.

## Notes

- The report is based on the latest rows in `claim_runs` and their associated `claim_stage_records`.
- The earlier TC001 misclassification was corrected before this final run.
- The evaluation runner is deterministic by design so the same input file produces the same results.