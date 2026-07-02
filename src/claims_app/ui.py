from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import streamlit as st

from claims_app.case_runner import run_cases_file
from claims_app.db import list_runs
from claims_app.models import ClaimInput, UploadedDocument
from claims_app.observability import configure_observability, langsmith_status
from claims_app.workflow import get_default_workflow


configure_observability()


def _stage_badge(status: str) -> str:
    mapping = {
        "passed": "#d1fae5",
        "warning": "#fef3c7",
        "failed": "#fee2e2",
        "pending": "#e5e7eb",
    }
    return mapping.get(status, "#e5e7eb")


def run() -> None:
    st.set_page_config(page_title="Claims Agentic Health", page_icon="🩺", layout="wide")
    st.markdown(
        """
        <style>
        .claim-card {
            padding: 1rem;
            border-radius: 1rem;
            border: 1px solid rgba(15, 23, 42, 0.08);
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        .stage-box {
            padding: 0.9rem 1rem;
            border-radius: 0.85rem;
            margin-bottom: 0.75rem;
            border: 1px solid rgba(15, 23, 42, 0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    workflow = get_default_workflow()
    claim_types = workflow.claim_types

    st.title("Health Insurance Claims Assistant")
    st.caption("Single-agent claims workflow with document validation, policy matching, and transparent decisioning.")

    tracing = langsmith_status()
    if tracing["ready"]:
        st.success(f"LangSmith tracing is configured for project: {tracing['project_name']}")
    else:
        st.warning("LangSmith tracing is not fully configured yet. Set LANGSMITH_API_KEY and LANGCHAIN_TRACING_V2=true in .env to see traces in LangSmith.")

    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.subheader("Submit Claim")
        with st.form("claim_form", clear_on_submit=False):
            member_id = st.text_input("Member ID", placeholder="EMP001")
            member_name = st.text_input("Member Name", placeholder="Asha Patel")
            treatment_type = st.selectbox("Treatment Type", claim_types)
            claimed_amount = st.number_input("Claimed Amount", min_value=0.0, value=1000.0, step=100.0)
            claim_date = st.date_input("Claim Date", value=date.today())
            provider_name = st.text_input("Provider / Hospital Name", placeholder="Apollo Hospital")
            notes = st.text_area("Notes", placeholder="Add pre-authorization details or other context.")
            documents = st.file_uploader(
                "Upload Documents",
                type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True,
            )
            submitted = st.form_submit_button("Evaluate Claim")

        if submitted:
            if not documents:
                st.error("Please upload at least one document before submitting the claim.")
                st.stop()

            uploaded_documents = [
                UploadedDocument(name=document.name, content_type=document.type or "application/octet-stream", data=document.getvalue())
                for document in documents
            ]
            claim = ClaimInput(
                member_id=member_id.strip(),
                member_name=member_name.strip() or None,
                treatment_type=treatment_type,
                claimed_amount=claimed_amount,
                claim_date=claim_date,
                provider_name=provider_name.strip() or None,
                notes=notes.strip() or None,
                documents=uploaded_documents,
            )
            with st.spinner("Evaluating claim..."):
                result = workflow.run(claim)
            st.session_state["last_result"] = result.model_dump()

    with right:
        st.subheader("What this system checks")
        st.markdown(
            """
            <div class="claim-card">
            <ol>
            <li><strong>Document validation</strong> confirms the right bill, prescription, report, or discharge file is uploaded.</li>
            <li><strong>Policy matching</strong> compares the claim against policy rules loaded from <code>policy_terms.json</code>.</li>
            <li><strong>Final decision</strong> returns approval, partial approval, rejection, manual review, or document error with confidence.</li>
            </ol>
            </div>
            """,
            unsafe_allow_html=True,
        )

    result_data = st.session_state.get("last_result")
    if result_data:
        st.divider()
        left_result, right_result = st.columns([0.9, 1.1], gap="large")
        with left_result:
            st.subheader("Decision")
            decision = result_data["decision"]
            if decision == "APPROVED":
                st.success(f"{decision}: {result_data['reason']}")
            elif decision == "PARTIAL":
                st.info(f"{decision}: {result_data['reason']}")
            elif decision == "MANUAL_REVIEW":
                st.warning(f"{decision}: {result_data['reason']}")
            else:
                st.error(f"{decision}: {result_data['reason']}")

            st.metric("Approved Amount", f"{result_data['approved_amount']:.2f}")
            st.metric("Confidence", f"{result_data['confidence']:.2%}")
            st.write(f"Trace reference: {result_data['trace_reference']}")

            st.subheader("Validation")
            validation = result_data["validation"]
            if validation["is_valid"]:
                st.success(validation["message"])
            else:
                st.error(validation["message"])
            st.json(validation)

        with right_result:
            st.subheader("Stage Trace")
            for record in result_data["stage_records"]:
                status = record["status"]
                color = _stage_badge(status)
                st.markdown(
                    f"""
                    <div class="stage-box" style="background:{color};">
                        <strong>{record['stage']}</strong><br/>
                        {record['message']}<br/>
                        <small>Status: {status}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.subheader("Policy Checks")
            st.json(result_data["policy_checks"])
            if result_data.get("extraction"):
                with st.expander("Extraction details"):
                    st.json(result_data["extraction"])

    st.divider()
    st.subheader("Assignment Test Case Runner")
    st.caption("Upload the assignment JSON file, run all cases locally, and inspect the SQLite-backed results below.")
    test_case_file = st.file_uploader("Upload test case JSON", type=["json"], key="test_case_json")
    if st.button("Run Uploaded Test Cases"):
        if test_case_file is None:
            st.error("Upload the test case JSON file first.")
        else:
            temp_path = Path("data/_uploaded_test_cases.json")
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(test_case_file.getvalue())
            results = run_cases_file(temp_path)
            st.session_state["assignment_results"] = [result.model_dump() for result in results]
            st.success(f"Ran {len(results)} test cases and stored the results in SQLite.")

    assignment_results = st.session_state.get("assignment_results")
    if assignment_results:
        st.subheader("Latest Test Case Results")
        st.dataframe(
            [
                {
                    "case_id": result["case_id"],
                    "case_name": result["case_name"],
                    "status": result["status"],
                    "decision": result.get("decision"),
                    "approved_amount": result.get("approved_amount"),
                    "confidence": result.get("confidence"),
                }
                for result in assignment_results
            ],
            use_container_width=True,
        )

    st.subheader("SQLite Runs")
    runs = list_runs(limit=50)
    if runs:
        st.dataframe(runs, use_container_width=True)
    else:
        st.info("No runs saved yet. Submit a claim or run the test cases to populate the local SQL database.")


if __name__ == "__main__":
    run()
