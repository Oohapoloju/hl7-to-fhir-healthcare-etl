"""Minimal HL7 v2 parser: splits a message into segments, fields and components."""
from __future__ import annotations

from dataclasses import dataclass


class HL7ParseError(ValueError):
    """Raised when the input is not a valid HL7 v2 message."""


@dataclass
class Segment:
    name: str
    fields: list[str]  # fields[0] is HL7 field 1 (for MSH, field 1 is the separator itself)
    component_sep: str = "^"

    def get(self, index: int, component: int = 1, default: str = "") -> str:
        """Return a 1-based field and component, or `default` when it is missing or empty."""
        if index < 1 or index > len(self.fields):
            return default
        parts = self.fields[index - 1].split(self.component_sep)
        if component < 1 or component > len(parts):
            return default
        return parts[component - 1] or default


@dataclass
class HL7Message:
    segments: list[Segment]

    def segment(self, name: str) -> Segment | None:
        return next((s for s in self.segments if s.name == name), None)

    def segments_named(self, name: str) -> list[Segment]:
        return [s for s in self.segments if s.name == name]

    @property
    def message_type(self) -> str:
        """Message type and trigger event from MSH-9, for example ADT^A01."""
        msh = self.segment("MSH")
        if msh is None:
            return ""
        code, event = msh.get(9, 1), msh.get(9, 2)
        return f"{code}^{event}" if event else code


def parse_message(raw: str) -> HL7Message:
    """Parse a raw HL7 v2 message (segments separated by CR, LF or CRLF)."""
    if not raw or not raw.strip():
        raise HL7ParseError("empty message")

    text = raw.replace("\r\n", "\r").replace("\n", "\r").strip()
    lines = [line for line in text.split("\r") if line.strip()]
    if not lines[0].startswith("MSH") or len(lines[0]) < 8:
        raise HL7ParseError("message must start with an MSH segment")

    field_sep = lines[0][3]
    encoding_chars = lines[0].split(field_sep)[1]
    component_sep = encoding_chars[0] if encoding_chars else "^"

    segments = []
    for line in lines:
        parts = line.split(field_sep)
        fields = parts[1:]
        if parts[0] == "MSH":
            fields = [field_sep] + fields
        segments.append(Segment(parts[0], fields, component_sep))
    return HL7Message(segments)
