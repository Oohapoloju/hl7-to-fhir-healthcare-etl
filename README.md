# HL7 v2 to FHIR R4 Healthcare ETL

![CI](https://github.com/Oohapoloju/hl7-to-fhir-healthcare-etl/actions/workflows/ci.yml/badge.svg)

A small, dependency-free **Python library** that parses HL7 v2 ADT messages and maps them to **FHIR R4** resources (Patient, Encounter) inside a Bundle. It is a demo built on synthetic messages and inspired by healthcare data-integration work (HL7/FHIR into a warehouse), not a copy of any employer's code.

## What it demonstrates

- **Robust parsing:** handles CR, LF and CRLF segment separators, custom encoding characters, empty fields and missing components without raising index errors.
- **Explicit error handling:** malformed input raises `HL7ParseError`; messages that cannot be mapped raise `MappingError` with a clear reason (missing PID, unsupported message type, invalid dates).
- **Correct data mapping:** HL7 dates to ISO-8601, gender codes to FHIR administrative gender, patient class to Encounter class, and identifiers sanitised into valid FHIR ids.
- **Testing discipline:** a pytest suite covers happy paths, edge cases and failure modes, run on Python 3.10 and 3.12 in GitHub Actions.

## Usage

```python
from hl7_fhir import parse_message, to_bundle

raw = (
    "MSH|^~\\&|SENDAPP|SENDFAC|RECVAPP|RECVFAC|20260101101500||ADT^A01|MSG0001|P|2.5\r"
    "PID|1||MRN12345^^^HOSP^MR||DOE^JANE||19850412|F"
)
bundle = to_bundle(parse_message(raw))
print(bundle["entry"][0]["resource"]["name"])   # [{'use': 'official', 'family': 'DOE', 'given': ['JANE']}]
```

## Mapping summary

| HL7 v2 field | FHIR R4 element |
| --- | --- |
| PID-3 (identifier, assigning authority) | `Patient.identifier`, `Patient.id` |
| PID-5 (name) | `Patient.name` (family, given) |
| PID-7 (birth date) | `Patient.birthDate` |
| PID-8 (sex) | `Patient.gender` |
| PV1-2 (patient class) | `Encounter.class` (IMP, AMB, EMER) |
| PV1-19 (visit number) | `Encounter.id` |
| PV1-44 (admit date/time) | `Encounter.period.start` |

## Project layout

```
src/hl7_fhir/parser.py   HL7 v2 parser (segments, fields, components)
src/hl7_fhir/mapper.py   HL7 to FHIR mapping and Bundle builder
tests/test_hl7_fhir.py   pytest suite
.github/workflows/ci.yml GitHub Actions (Python 3.10 and 3.12)
```

## Run the tests

```
pip install pytest
pytest -q
```

## Scope and next steps

This is an intentionally small reference implementation. Production pipelines would add:

- [ ] More message types (ORU lab results, ORM orders) and segments (OBX, AL1)
- [ ] FHIR schema validation of generated resources
- [ ] Streaming ingestion (Kafka) and loading into a warehouse such as Snowflake
- [ ] De-identification and audit logging for PHI

## Author

Ooha Poloju - Software Engineer (Java, Kafka, Azure, AWS). LinkedIn: https://www.linkedin.com/in/ooha-poloju-3b7b42435/
