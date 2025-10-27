from __future__ import annotations

import re

from django.db import transaction

from voters.models import IDDocument, Voter
from voters.services.ocr import extract_text, normalize_digits


class DocumentProcessingError(Exception):
    """Raised when OCR processing fails unexpectedly."""


def process_document(document: IDDocument) -> IDDocument:
    """Run OCR checks against an uploaded document and persist validation results."""
    try:
        processed_path = document.image.path
        raw_text = extract_text(document.image.path, processed_path=processed_path)
    except Exception as exc:  # pragma: no cover - easyocr internal errors
        raise DocumentProcessingError(f"تعذر قراءة الصورة: {exc}") from exc

    normalized_text = normalize_digits(raw_text)
    text_no_whitespace = re.sub(r"\s+", "", normalized_text)
    errors: list[str] = []

    if len(normalized_text.strip()) < 8:
        errors.append("لم يتم التعرف على نص كافٍ من الصورة.")

    if document.document_type == IDDocument.DocumentType.NATIONAL_ID:
        errors.extend(_validate_national_id(document.voter, normalized_text))
    elif document.document_type == IDDocument.DocumentType.VOTER_CARD:
        errors.extend(_validate_voter_card(document.voter, text_no_whitespace))

    document.extracted_text = normalized_text
    document.validation_status = "passed" if not errors else "failed"
    document.validation_errors = "\n".join(errors)
    document.save(
        update_fields=["extracted_text", "validation_status", "validation_errors"]
    )

    return document


def _validate_national_id(voter: Voter, text: str) -> list[str]:
    digits = re.findall(r"\d+", text)
    if not digits:
        return ["تعذر استخراج رقم الهوية الوطنية من الصورة."]

    digits.sort(key=len, reverse=True)
    id_number = digits[0]
    errors: list[str] = []
    if len(id_number) < 10:
        errors.append("رقم الهوية الوطنية المكتشف أقصر من المتوقع.")

    year_fragment = id_number[:4]
    if year_fragment.isdigit():
        year_int = int(year_fragment)
        if 1900 <= year_int <= 2100:
            if voter.birth_year and voter.birth_year != year_int:
                errors.append(
                    f"سنة الميلاد في الهوية ({year_fragment}) لا تطابق بيانات الناخب ({voter.birth_year})."
                )
            elif not voter.birth_year:
                voter.birth_year = year_int
                voter.save(update_fields=["birth_year"])
        else:
            errors.append("الأرقام الأولى من رقم الهوية لا تمثل سنة ميلاد صحيحة.")
    else:
        errors.append("تعذر قراءة سنة الميلاد من رقم الهوية.")

    stored_national_id = re.sub(r"\D", "", voter.national_id_number or "")
    extracted_clean = re.sub(r"\D", "", id_number)
    if stored_national_id:
        if stored_national_id not in extracted_clean:
            errors.append("رقم الهوية الوطنية لا يطابق الرقم المسجل في النظام.")
    else:
        # Persist the full number for future comparisons when it seems complete.
        if len(extracted_clean) >= 10:
            voter.national_id_number = extracted_clean
            voter.save(update_fields=["national_id_number"])

    return errors


def _validate_voter_card(voter: Voter, text_no_whitespace: str) -> list[str]:
    voter_digits = re.sub(r"\D", "", voter.voter_number)
    text_digits = re.sub(r"\D", "", text_no_whitespace)
    if not voter_digits:
        return ["لا يحتوي رقم الناخب في النظام على أرقام يمكن مطابقتها."]
    if voter_digits not in text_digits:
        return ["رقم الناخب في بطاقة الناخب لا يطابق الرقم الموجود في النظام."]
    return []


def process_document_pair(national_doc: IDDocument, voter_doc: IDDocument):
    with transaction.atomic():
        process_document(national_doc)
        process_document(voter_doc)
