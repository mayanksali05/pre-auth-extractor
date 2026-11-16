from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import fitz  # PyMuPDF
import boto3
import tempfile
import os
import re
import urllib.request

app = FastAPI()


class ExtractionResponse(BaseModel):
    authorization_meta: dict
    patient_details: dict
    treatment_details: dict


class PDFInput(BaseModel):
    pdf_url: str


def download_pdf(pdf_url: str) -> str:
    """Download PDF from S3/HTTP URL or use local path. Returns temp file path."""
    if pdf_url.startswith("s3://"):
        parts = pdf_url[5:].split("/", 1)
        bucket_name, key = parts[0], parts[1] if len(parts) > 1 else ""
        s3 = boto3.client("s3")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        s3.download_file(bucket_name, key, tmp.name)
        tmp.close()
        return tmp.name
    elif pdf_url.startswith("http://") or pdf_url.startswith("https://"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        urllib.request.urlretrieve(pdf_url, tmp.name)
        tmp.close()
        return tmp.name
    else:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        with open(pdf_url, "rb") as src:
            tmp.write(src.read())
        tmp.close()
        return tmp.name


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from PDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def find_field(text: str, patterns: list, default=None) -> str:
    """Try multiple regex patterns; return first match or default."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            val = match.group(1) if (match.lastindex is not None and match.lastindex >= 1) else match.group(0)
            val = val.strip()
            val = re.sub(r'\s+\*?\s*$', '', val)
            return val
    return default


def extract_tpa_name_from_doc(text: str) -> str:
    """Extract TPA name from PDF document text."""
    patterns = [
        r"Name of TPA[:\s]+(.+?)(?=\n|$)",
        r"Name of Insurance Company[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_patient_name(text: str) -> str:
    """Extract patient name."""
    patterns = [
        r"Patient Name[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_policy_number(text: str) -> str:
    """Extract policy number."""
    patterns = [
        r"Policy Number[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_approved_amount(text: str) -> str:
    """Extract approved/authorized amount."""
    patterns = [
        r"Total Authorised Amount[:\s]+([0-9,]+)",
        r"Authorized[:\s]+([0-9,]+)",
    ]
    return find_field(text, patterns, "")


def extract_admission_date(text: str) -> str:
    """Extract admission/validity date."""
    patterns = [
        r"Expected Date of Admission[:\s]+(\d{2}[\/-]\d{2}[\/-]\d{4})",
        r"Admission Date[:\s]+(\d{2}[\/-]\d{2}[\/-]\d{4})",
        r"valid for admission up to (\d{2}[\/-]\d{2}[\/-]\d{4})",
    ]
    return find_field(text, patterns, "")


def extract_discharge_date(text: str) -> str:
    """Extract discharge date."""
    patterns = [
        r"Expected Date of Discharge[:\s]+(\d{2}[\/-]\d{2}[\/-]\d{4})",
        r"Date of Discharge[:\s]+(\d{2}[\/-]\d{2}[\/-]\d{4})",
        r"Discharge date[:\s]+(\d{2}[\/-]\d{2}[\/-]\d{4})",
    ]
    return find_field(text, patterns, "")


def extract_diagnosis(text: str) -> str:
    """Extract provisional diagnosis."""
    patterns = [
        r"Provisional Diagnosis[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_procedure(text: str) -> str:
    """Extract planned procedure/treatment."""
    patterns = [
        r"Proposed line of treatment[:\s]+(.+?)(?=\n|$)",
        r"surgical management[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_room_category_occupied(text: str) -> str:
    """Extract room category occupied."""
    patterns = [
        r"Room category[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_length_of_stay(text: str) -> str:
    """Extract length of stay."""
    patterns = [
        r"Expected Length of Stay[:\s]+(\d+)",
        r"length of stay[:\s]+(\d+)",
        r"(\d+)\s+days",
    ]
    return find_field(text, patterns, "")


def extract_eligible_room_category(text: str) -> str:
    """Extract eligible room category."""
    patterns = [
        r"Eligible Room Category as per T[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_treating_doctor(text: str) -> str:
    """Extract treating doctor."""
    patterns = [
        r" treating doctor[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_rohini_id(text: str) -> str:
    """Extract RIHINO ID."""
    patterns = [
        r"Rohini Id[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_request_reference(text: str) -> str:
    """Extract request/reference number."""
    patterns = [
        r"Claim Number[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_insurance_company(text: str) -> str:
    """Extract insurance company name."""
    patterns = [
        r"Name of Insurance Company[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_relation(text: str) -> str:
    """Extract relation to primary beneficiary."""
    patterns = [
        r"Relation with Proposer[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_gender(text: str) -> str:
    """Extract gender."""
    patterns = [
        r"Gender[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_age(text: str) -> str:
    """Extract age."""
    patterns = [
        r"Age[:\s]+(\d+)",
    ]
    return find_field(text, patterns, "")


def extract_policy_holder(text: str) -> str:
    """Extract policy holder/proposer name."""
    patterns = [
        r"Proposer Name[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_primary_beneficiary(text: str) -> str:
    """Extract primary beneficiary."""
    patterns = [
        r"Primary Beneficiary[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_medi_assist_id(text: str) -> str:
    """Extract Medi Assist ID (now unused, kept for backward compatibility)."""
    patterns = [
        r"Medi Assist Id[:\s]+(.+?)(?=\n|$)",
    ]
    return find_field(text, patterns, "")


def extract_requested_amount(text: str) -> str:
    """Extract requested amount."""
    patterns = [
        r"Requested Amount[:\s]+([0-9,]+)",
    ]
    return find_field(text, patterns, "")


def extract_hospital_name(text: str) -> str:
    """Extract hospital name."""
    patterns = [
        r"Apollo Speciality[^\n]*",
    ]
    return find_field(text, patterns, "")


def extract_hospital_id(text: str) -> str:
    """Extract hospital ID."""
    patterns = [
        r"Rohini Id[:\s]+(\S+)",
    ]
    return find_field(text, patterns, "")


def extract_authorization_type(text: str) -> str:
    """Extract authorization type."""
    patterns = [
        r"Authorization is valid[^\n]*",
    ]
    return find_field(text, patterns, "")


def extract_policy_period(text: str) -> dict:
    """Extract policy period start/end dates."""
    start = find_field(text, [r"Policy Period[:\s]+(.+?)(?=\n|$)"], "")
    end = find_field(text, [
        r"\d{2}[-/]\d{2}[-/]\d{4}",
    ], "")

    if start and end:
        return {"start_date": start, "end_date": end}
    return {"start_date": start, "end_date": ""}


def extract_all_fields(text: str) -> dict:
    """Extract all required fields from PDF text into the common schema."""
    tpa_name = extract_tpa_name_from_doc(text)
    return {
        "authorization_meta": {
            "date": extract_admission_date(text),
            "authorization_type": extract_authorization_type(text),
            "hospital_name": extract_hospital_name(text),
            "hospital_id": extract_hospital_id(text),
            "rohini_id": extract_rohini_id(text),
            "request_reference_number": extract_request_reference(text),
            "requested_amount_body": extract_requested_amount(text),
            "authorized_amount_body": extract_approved_amount(text),
            "admission_validity_date": extract_admission_date(text),
        },
        "patient_details": {
            "patient_name": extract_patient_name(text),
            "tpa_name": tpa_name,
            "age": extract_age(text),
            "gender": extract_gender(text),
            "insurance_company": extract_insurance_company(text),
            "policy_holder": extract_policy_holder(text),
            "policy_no": extract_policy_number(text),
            "primary_beneficiary": extract_primary_beneficiary(text),
            "policy_period": extract_policy_period(text),
        },
        "treatment_details": {
            "provisional_diagnosis": extract_diagnosis(text),
            "admission_date": extract_admission_date(text),
            "procedure_treatment_planned": extract_procedure(text),
            "discharge_date": extract_discharge_date(text),
            "room_category_occupied": extract_room_category_occupied(text),
            "length_of_stay": extract_length_of_stay(text),
            "eligible_room_category": extract_eligible_room_category(text),
            "treating_doctor": extract_treating_doctor(text),
        },
    }


def extract_data(pdf_url: str) -> ExtractionResponse:
    """Main extraction function - downloads PDF and extracts all fields."""
    pdf_path = download_pdf(pdf_url)
    try:
        text = extract_text_from_pdf(pdf_path)
        data = extract_all_fields(text)
        # Ensure all expected keys exist (fill null if missing)
        default_response = {
            "authorization_meta": {
                "date": None,
                "authorization_type": None,
                "hospital_name": None,
                "hospital_id": None,
                "rohini_id": None,
                "request_reference_number": None,
                "requested_amount_body": None,
                "authorized_amount_body": None,
                "admission_validity_date": None,
            },
            "patient_details": {
                "patient_name": None,
                "tpa_name": None,
                "age": None,
                "gender": None,
                "insurance_company": None,
                "policy_holder": None,
                "policy_no": None,
                "primary_beneficiary": None,
                "policy_period": {"start_date": None, "end_date": None},
            },
            "treatment_details": {
                "provisional_diagnosis": None,
                "admission_date": None,
                "procedure_treatment_planned": None,
                "discharge_date": None,
                "room_category_occupied": None,
                "length_of_stay": None,
                "eligible_room_category": None,
                "treating_doctor": None,
            },
        }
        # Merge: keep found values, fill missing with null
        result = {}
        for section in default_response:
            result[section] = {}
            for key in default_response[section]:
                result[section][key] = data.get(section, {}).get(key, default_response[section][key])
        return result
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


@app.post("/extract", response_model=ExtractionResponse)
async def extract_endpoint(input_data: PDFInput):
    try:
        result = extract_data(input_data.pdf_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))