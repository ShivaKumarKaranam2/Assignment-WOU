# Component Contracts

This document defines the observable interface for each significant component in the claims system. Another engineer should be able to reimplement one component from this description alone.

## 1. Configuration Loader

### Component
`Settings`

### Accepts
- Environment variables loaded from `.env`
- Defaults for local development

### Produces
- A typed settings object with policy file path, tracing settings, model identifiers, and upload limits

### Errors
- Invalid environment values during parsing
- Missing values are tolerated when defaults exist, but tracing remains disabled when no LangSmith key is present

## 2. Policy Repository

### Component
`PolicyRepository`

### Accepts
- Path to `policy_terms.json`

### Produces
- Policy metadata
- Claim rules for a treatment type
- Required documents for a treatment type
- Document keyword mappings
- Member records
- Parsed dates

### Errors
- File missing or unreadable
- Invalid JSON structure
- Unknown claim type when requesting claim rules or required documents
- Unknown member lookup may return `None` when the component can safely continue

### Key Interface Methods
- `claim_rule(claim_type: str) -> dict`
- `required_documents(claim_type: str) -> list[str]`
- `document_keywords() -> dict[str, list[str]]`
- `find_member(member_id: str, member_name: str | None) -> dict | None`
- `parse_date(value: str) -> date`

## 3. OCR Service

### Component
`OCRService`

### Accepts
- Uploaded documents with file name, content type, and bytes
- Policy document keywords for classification

### Produces
- A list of OCR documents containing text, quality score, category, and source metadata

### Errors
- HTTP or network errors from the external OCR endpoint
- Unsupported content types
- Decode failures
- Unreadable files, which should be returned as OCR documents with an error field rather than crashing the workflow

### Contract Notes
- The service must always return one result per input document
- If a file cannot be read, the output must preserve the file name and report the failure in the `error` field

## 4. Extraction Service

### Component
`ExtractionService`

### Accepts
- Claim input data
- OCR documents
- Policy rule context

### Produces
- Structured extraction data such as patient name, bill amount, diagnosis, treatment, and evidence quality

### Errors
- LLM client failure
- JSON parse failure from model output
- Missing or incomplete OCR text

### Contract Notes
- The service must fall back to heuristic extraction when the LLM is unavailable
- The returned extraction object must include a quality score and a degraded flag when confidence is reduced

## 5. Claim Workflow

### Component
`ClaimWorkflow`

### Accepts
- A `ClaimInput` with member details, treatment type, amount, date, optional notes, and uploaded documents

### Produces
- A `ClaimResult` containing:
- final decision
- approved amount
- reason
- confidence
- stage records
- validation output
- extraction output
- policy checks
- trace reference

### Errors
- Unsupported claim type
- Missing policy rule
- Missing member record
- OCR or extraction degradation
- Internal stage exceptions should be converted into a safe result rather than crashing the process

### Stage Behavior
- Stage 1 validates document type, completeness, and readability
- Stage 2 matches policy rules and computes approval logic
- Stage 3 turns the policy result into the final decision object

## 6. FastAPI Service

### Component
`FastAPI app`

### Accepts
- HTTP requests for health checks, claim submission, trace lookup, run history, and assignment batch execution

### Produces
- JSON responses that mirror the claim result or run summary

### Errors
- 400 for missing required files or malformed inputs
- 404 for unknown claims or run ids
- 413 for oversized uploads
- 500 only for unexpected server-side failures

### Endpoint Contract Summary
- `GET /health` returns status and LangSmith readiness
- `POST /claims/submit` accepts multipart claim data and returns a claim decision
- `GET /claims/{claim_id}` returns a stored claim result
- `GET /claims/{claim_id}/trace` returns stage trace data for a claim
- `GET /runs` returns the latest persisted run summaries
- `GET /runs/{run_id}` returns a persisted run with stage records
- `POST /assignment/run` evaluates the provided test case payload

## 7. Streamlit UI

### Component
`Streamlit UI`

### Accepts
- User form input
- Uploaded medical documents
- Uploaded assignment test-case JSON

### Produces
- An interactive decision display
- Validation output
- Stage trace cards
- Policy check data
- Extraction details
- SQLite run table
- Assignment test-case result table

### Errors
- Missing uploads
- Local file write failure when staging uploaded test cases
- Upstream backend or workflow failure, which should be surfaced in the UI instead of hidden

## 8. SQLite Persistence Layer

### Component
`SQLite persistence layer`

### Accepts
- Assignment case results
- Live claim results
- Stage records

### Produces
- Rows in `claim_runs`
- Rows in `claim_stage_records`
- Queryable run summaries and run detail records

### Errors
- Database file creation failure
- SQL write failure
- Corrupt database file

### Contract Notes
- Writes should be idempotent per run id because each run overwrites the previous row with the same identifier
- Stage records must be persisted alongside the parent run

## 9. Observability Bootstrap

### Component
`configure_observability()`

### Accepts
- Runtime settings

### Produces
- Environment variables required for LangSmith tracing
- A readiness status for the UI and health endpoint

### Errors
- Missing API key means tracing is not ready
- Misconfigured project name means traces may go to the wrong project

## 10. Assignment Case Runner

### Component
`AssignmentCaseRunner`

### Accepts
- A test case dictionary from the assignment JSON

### Produces
- An [AssignmentCaseResult](src/claims_app/models.py) with decision, confidence, message, stage records, and trace reference

### Errors
- Missing case fields may fall back to defaults
- Unsupported or malformed case input may return a manual-review or document-error style result depending on the failure mode

### Deterministic Behavior
- TC001–TC012 must produce stable, reproducible outcomes
- The runner must persist each case result to SQLite
- The runner must not depend on external OCR or LLM calls for the assignment payloads

## 11. Shared Data Models

### Component
`Shared data models`

### Accepts
- Structured Python values populated by the workflow or batch runner

### Produces
- Typed models for stages, documents, validation, policy checks, claim results, assignment summaries, and assignment case results

### Errors
- Validation errors from Pydantic when required fields are missing or malformed

## 12. Contract Boundaries Worth Preserving

- UI code must not contain claim logic
- Policy logic must not be hardcoded in the frontend
- The assignment runner must remain separate from live OCR-based claim evaluation
- The workflow must preserve stage records even when the final result is a failure
- Tracing must never be required for correct business behavior