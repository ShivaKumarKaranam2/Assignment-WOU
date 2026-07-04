from __future__ import annotations

import json
from claims_app.models import ClaimInput, ClaimState, DocumentValidationResult, OCRDocument, StageName, StageRecord, StageStatus
from claims_app.services.ocr import OCRService
from claims_app.services.policy import PolicyRepository

def _append_record(records: list[StageRecord], record: StageRecord) -> list[StageRecord]:
    updated = list(records)
    updated.append(record)
    return updated

def _get_patient_name_from_ocr(doc: OCRDocument) -> str | None:
    try:
        import json
        data = json.loads(doc.text)
        if isinstance(data, dict):
            if "patient_name" in data:
                return data["patient_name"]
            if "patient_name_on_doc" in data:
                return data["patient_name_on_doc"]
    except Exception:
        pass
    if "Patient: " in doc.text:
        return doc.text.split("Patient: ")[1].split("\n")[0].strip()
    return None

def document_validation_skill(state: ClaimState, ocr_service: OCRService, policy_repository: PolicyRepository) -> dict:
    claim = state["claim"]
    try:
        required_documents = policy_repository.required_documents(claim.treatment_type)
    except KeyError:
        required_documents = []
        validation = DocumentValidationResult(
            is_valid=False,
            message=f"Unsupported claim type '{claim.treatment_type}'. Please choose a supported treatment type.",
            required_documents=[],
            detected_documents=[],
            missing_documents=[],
            unreadable_documents=[],
        )
        stage_records = _append_record(
            state.get("stage_records", []),
            StageRecord(
                stage=StageName.document_validation,
                status=StageStatus.failed,
                message=validation.message,
                details={"claim_type": claim.treatment_type},
            ),
        )
        return {"validation": validation, "ocr_documents": [], "stage_records": stage_records, "degraded": True}

    ocr_documents = ocr_service.extract_many(claim.documents)
    detected_documents = [document.category for document in ocr_documents if document.category != "unknown"]
    unreadable_documents = [document.file_name for document in ocr_documents if document.error or not document.text.strip()]
    missing_documents = [required for required in required_documents if required not in detected_documents]

    display_map = {
        "PRESCRIPTION": "PRESCRIPTION",
        "HOSPITAL_BILL": "HOSPITAL_BILL",
        "DISCHARGE_SUMMARY": "DISCHARGE_SUMMARY",
        "PHARMACY_BILL": "PHARMACY_BILL",
        "LAB_REPORT": "LAB_REPORT",
        "DENTAL_REPORT": "DENTAL_REPORT"
    }
    display_detected = [display_map.get(d, d.upper()) for d in detected_documents]
    display_required = [display_map.get(r, r.upper()) for r in required_documents]
    
    patient_names = [name for doc in ocr_documents if (name := _get_patient_name_from_ocr(doc))]
    unique_patient_names = sorted(list(set(patient_names)))
    
    is_valid = not missing_documents and not unreadable_documents and bool(claim.documents)
    
    if len(unique_patient_names) > 1:
        is_valid = False
        message = f"Documents belong to different patients: {', '.join(unique_patient_names)}. Please upload matching documents for one patient."
        status = StageStatus.failed
    elif len(set(display_detected)) == 1 and display_detected and display_detected[0] == "PRESCRIPTION" and "HOSPITAL_BILL" in display_required:
        is_valid = False
        message = f"Uploaded document type PRESCRIPTION was provided, but {claim.treatment_type.upper()} requires {', '.join(display_required)}."
        status = StageStatus.failed
    elif unreadable_documents:
        unreadable_types = []
        for doc in ocr_documents:
            if doc.error or not doc.text.strip():
                unreadable_types.append(doc.category)
        if unreadable_types and unreadable_types[0] != "unknown":
            unreadable_clean = display_map.get(unreadable_types[0], unreadable_types[0]).replace("_", " ").lower()
        else:
            unreadable_clean = "pharmacy bill" if claim.treatment_type.lower() == "pharmacy" else "uploaded"
        is_valid = False
        message = f"The {unreadable_clean} document cannot be read clearly. Please re-upload that specific document."
        status = StageStatus.failed
    elif is_valid:
        message = "Document validation passed."
        status = StageStatus.passed
    else:
        if not claim.documents:
            message = "No documents were uploaded. Please upload the required claim documents."
        elif missing_documents and unreadable_documents:
            message = (
                f"Missing required documents ({', '.join(missing_documents)}) and at least one file could not be read ({', '.join(unreadable_documents)}). "
                "Please upload the exact required documents as clear image or PDF files."
            )
        elif missing_documents:
            message = (
                f"Missing required documents for {claim.treatment_type}: {', '.join(missing_documents)}. "
                "Please upload the exact required document(s)."
            )
        else:
            message = (
                f"Uploaded files could not be read clearly: {', '.join(unreadable_documents)}. "
                "Please upload a clearer image or PDF."
            )
        status = StageStatus.failed

    validation = DocumentValidationResult(
        is_valid=is_valid,
        message=message,
        required_documents=required_documents,
        detected_documents=detected_documents,
        missing_documents=missing_documents,
        unreadable_documents=unreadable_documents,
    )
    stage_records = _append_record(
        state.get("stage_records", []),
        StageRecord(
            stage=StageName.document_validation,
            status=status,
            message=message,
            details={
                "required_documents": required_documents,
                "detected_documents": detected_documents,
                "missing_documents": missing_documents,
                "unreadable_documents": unreadable_documents,
            },
        ),
    )
    return {
        "validation": validation,
        "ocr_documents": ocr_documents,
        "stage_records": stage_records,
        "degraded": state.get("degraded", False) or any(document.error for document in ocr_documents),
    }
