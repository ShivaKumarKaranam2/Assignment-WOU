from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import fitz
import requests

from claims_app.config import settings
from claims_app.models import OCRDocument, UploadedDocument
from claims_app.services.policy import PolicyRepository


OCR_URL = "https://ai.api.nvidia.com/v1/cv/nvidia/nemotron-ocr-v2"


def _find_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        parts = [_find_text(item) for item in payload]
        return "\n".join(part for part in parts if part)
    if isinstance(payload, dict):
        preferred_keys = ("text", "markdown", "content", "result", "response")
        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        parts = [_find_text(value) for value in payload.values()]
        joined = "\n".join(part for part in parts if part)
        if joined.strip():
            return joined.strip()
    return ""


def classify_document(file_name: str, text: str, keywords: dict[str, list[str]]) -> str:
    haystack = f"{file_name} {text}".lower()
    best_category = "unknown"
    best_score = 0
    for category, category_keywords in keywords.items():
        score = sum(1 for keyword in category_keywords if keyword.lower() in haystack)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


def document_quality_score(text: str, file_size: int) -> float:
    if file_size <= 0:
        return 0.0
    density = min(len(text) / max(file_size / 40.0, 1.0), 1.0)
    return round(density, 3)


@dataclass
class OCRService:
    policy_repository: PolicyRepository
    api_key: str = settings.nvidia_ocr_api_key

    def extract(self, document: UploadedDocument) -> OCRDocument:
        if document.content_type == "application/pdf" or document.name.lower().endswith(".pdf"):
            return self._extract_pdf(document)
        return self._extract_image(document)

    def extract_many(self, documents: list[UploadedDocument]) -> list[OCRDocument]:
        return [self.extract(document) for document in documents]

    def _extract_image(self, document: UploadedDocument) -> OCRDocument:
        try:
            encoded = base64.b64encode(document.data).decode("utf-8")
            payload = {
                "input": [
                    {
                        "type": "image_url",
                        "url": f"data:{document.content_type};base64,{encoded}",
                    }
                ]
            }
            response = requests.post(
                OCR_URL,
                headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
            payload_data = response.json()
            text = _find_text(payload_data) or json.dumps(payload_data)
            category = classify_document(document.name, text, self.policy_repository.document_keywords())
            return OCRDocument(
                file_name=document.name,
                content_type=document.content_type,
                text=text,
                source="nvidia_ocr",
                quality_score=document_quality_score(text, len(document.data)),
                category=category,
            )
        except Exception as exc:  # pragma: no cover - network failure path
            return OCRDocument(
                file_name=document.name,
                content_type=document.content_type,
                text="",
                source="nvidia_ocr",
                quality_score=0.0,
                error=str(exc),
                category="unknown",
            )

    def _extract_pdf(self, document: UploadedDocument) -> OCRDocument:
        try:
            pdf = fitz.open(stream=document.data, filetype="pdf")
            page_texts: list[str] = []
            for page in pdf:
                extracted = page.get_text("text") or ""
                if extracted.strip():
                    page_texts.append(extracted)
                    continue
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image_bytes = pixmap.tobytes("png")
                image_doc = UploadedDocument(name=f"{document.name}_page.png", content_type="image/png", data=image_bytes)
                image_result = self._extract_image(image_doc)
                page_texts.append(image_result.text)
            text = "\n\n".join(part for part in page_texts if part).strip()
            category = classify_document(document.name, text, self.policy_repository.document_keywords())
            return OCRDocument(
                file_name=document.name,
                content_type=document.content_type,
                text=text,
                source="pdf_text_or_ocr",
                quality_score=document_quality_score(text, len(document.data)),
                category=category,
            )
        except Exception as exc:
            return OCRDocument(
                file_name=document.name,
                content_type=document.content_type,
                text="",
                source="pdf_text_or_ocr",
                quality_score=0.0,
                error=str(exc),
                category="unknown",
            )
