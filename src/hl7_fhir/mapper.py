"""Map HL7 v2 ADT messages to FHIR R4 resources (Patient, Encounter) and a Bundle."""
from __future__ import annotations

import re
from datetime import datetime

from .parser import HL7Message

DEFAULT_ID_SYSTEM = "urn:oid:2.16.840.1.113883.19.5"  # example OID for synthetic data

GENDER_MAP = {"M": "male", "F": "female", "O": "other", "A": "other", "U": "unknown"}
ENCOUNTER_CLASS_MAP = {
    "I": ("IMP", "inpatient encounter"),
    "O": ("AMB", "ambulatory"),
    "E": ("EMER", "emergency"),
}


class MappingError(ValueError):
    """Raised when a message cannot be mapped to FHIR."""


def hl7_datetime_to_iso(value: str) -> str | None:
    """Convert HL7 YYYYMMDD[HHMM[SS]] to an ISO-8601 date or date-time string."""
    if not value:
        return None
    for fmt, length in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8)):
        if len(value) == length:
            try:
                parsed = datetime.strptime(value, fmt)
            except ValueError:
                break
            return parsed.date().isoformat() if length == 8 else parsed.isoformat()
    raise MappingError(f"invalid HL7 date/time: {value!r}")


def _fhir_id(value: str) -> str:
    # FHIR ids allow only letters, digits, '-' and '.', max 64 characters.
    return re.sub(r"[^A-Za-z0-9.-]", "-", value)[:64]


def map_patient(message: HL7Message) -> dict:
    pid = message.segment("PID")
    if pid is None:
        raise MappingError("PID segment is required")

    mrn = pid.get(3, 1)
    if not mrn:
        raise MappingError("PID-3 patient identifier is required")

    patient: dict = {
        "resourceType": "Patient",
        "id": _fhir_id(mrn),
        "identifier": [{"system": pid.get(3, 4) and f"urn:id:{pid.get(3, 4)}" or DEFAULT_ID_SYSTEM, "value": mrn}],
    }

    family, given = pid.get(5, 1), pid.get(5, 2)
    if family or given:
        name: dict = {"use": "official"}
        if family:
            name["family"] = family
        if given:
            name["given"] = [given]
        patient["name"] = [name]

    birth_date = hl7_datetime_to_iso(pid.get(7))
    if birth_date:
        patient["birthDate"] = birth_date

    patient["gender"] = GENDER_MAP.get(pid.get(8).upper(), "unknown")
    return patient


def map_encounter(message: HL7Message, patient_id: str) -> dict | None:
    pv1 = message.segment("PV1")
    if pv1 is None:
        return None

    code, display = ENCOUNTER_CLASS_MAP.get(pv1.get(2).upper(), ("AMB", "ambulatory"))
    encounter: dict = {
        "resourceType": "Encounter",
        "status": "in-progress",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": code,
            "display": display,
        },
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    visit_number = pv1.get(19)
    if visit_number:
        encounter["id"] = _fhir_id(visit_number)
    admit = hl7_datetime_to_iso(pv1.get(44))
    if admit:
        encounter["period"] = {"start": admit}
    return encounter


def to_bundle(message: HL7Message) -> dict:
    """Convert an ADT message into a FHIR collection Bundle."""
    if not message.message_type.startswith("ADT"):
        raise MappingError(f"unsupported message type: {message.message_type or 'unknown'}")

    patient = map_patient(message)
    entries = [{"resource": patient}]
    encounter = map_encounter(message, patient["id"])
    if encounter:
        entries.append({"resource": encounter})
    return {"resourceType": "Bundle", "type": "collection", "entry": entries}
