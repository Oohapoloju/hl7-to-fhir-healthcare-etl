import pytest

from hl7_fhir import HL7ParseError, MappingError, map_patient, parse_message, to_bundle
from hl7_fhir.mapper import hl7_datetime_to_iso


def build_pv1(patient_class="I", visit="V0001", admit="20260101101000"):
    fields = [""] * 44
    fields[0], fields[1], fields[18], fields[43] = "1", patient_class, visit, admit
    return "PV1|" + "|".join(fields)


def adt_message(message_type="ADT^A01", pid=None, pv1=None, sep="\r"):
    pid = pid if pid is not None else "PID|1||MRN12345^^^HOSP^MR||DOE^JANE||19850412|F"
    msh = f"MSH|^~\\&|SENDAPP|SENDFAC|RECVAPP|RECVFAC|20260101101500||{message_type}|MSG0001|P|2.5"
    segments = [msh, pid, pv1 if pv1 is not None else build_pv1()]
    return sep.join(s for s in segments if s)


def test_parser_reads_segments_fields_and_components():
    message = parse_message(adt_message())
    assert [s.name for s in message.segments] == ["MSH", "PID", "PV1"]
    assert message.message_type == "ADT^A01"
    pid = message.segment("PID")
    assert pid.get(5, 1) == "DOE"
    assert pid.get(5, 2) == "JANE"
    assert pid.get(99, default="n/a") == "n/a"


def test_parser_accepts_newline_separated_messages():
    message = parse_message(adt_message(sep="\n") + "\n")
    assert message.segment("PID") is not None


@pytest.mark.parametrize("raw", ["", "   ", "PID|1||X", "MS"])
def test_parser_rejects_invalid_messages(raw):
    with pytest.raises(HL7ParseError):
        parse_message(raw)


def test_map_patient_builds_fhir_patient():
    patient = map_patient(parse_message(adt_message()))
    assert patient["resourceType"] == "Patient"
    assert patient["id"] == "MRN12345"
    assert patient["identifier"] == [{"system": "urn:id:HOSP", "value": "MRN12345"}]
    assert patient["name"] == [{"use": "official", "family": "DOE", "given": ["JANE"]}]
    assert patient["birthDate"] == "1985-04-12"
    assert patient["gender"] == "female"


def test_unknown_gender_code_maps_to_unknown():
    pid = "PID|1||MRN1^^^HOSP||DOE^JANE||19850412|X"
    assert map_patient(parse_message(adt_message(pid=pid)))["gender"] == "unknown"


def test_bundle_contains_patient_and_encounter():
    bundle = to_bundle(parse_message(adt_message()))
    assert bundle["resourceType"] == "Bundle"
    patient, encounter = (entry["resource"] for entry in bundle["entry"])
    assert encounter["resourceType"] == "Encounter"
    assert encounter["id"] == "V0001"
    assert encounter["class"]["code"] == "IMP"
    assert encounter["subject"] == {"reference": f"Patient/{patient['id']}"}
    assert encounter["period"] == {"start": "2026-01-01T10:10:00"}


def test_bundle_without_pv1_has_only_the_patient():
    bundle = to_bundle(parse_message(adt_message(pv1="")))
    assert [entry["resource"]["resourceType"] for entry in bundle["entry"]] == ["Patient"]


def test_missing_pid_is_a_mapping_error():
    message = parse_message("MSH|^~\\&|A|B|C|D|20260101||ADT^A01|1|P|2.5")
    with pytest.raises(MappingError):
        to_bundle(message)


def test_non_adt_messages_are_rejected():
    with pytest.raises(MappingError):
        to_bundle(parse_message(adt_message(message_type="ORU^R01")))


@pytest.mark.parametrize(
    "value, expected",
    [
        ("20260131", "2026-01-31"),
        ("202601311230", "2026-01-31T12:30:00"),
        ("20260131123045", "2026-01-31T12:30:45"),
        ("", None),
    ],
)
def test_hl7_datetime_conversion(value, expected):
    assert hl7_datetime_to_iso(value) == expected


@pytest.mark.parametrize("value", ["2026", "20261301", "not-a-date"])
def test_invalid_dates_raise_mapping_error(value):
    with pytest.raises(MappingError):
        hl7_datetime_to_iso(value)
