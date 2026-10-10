"""Normalized document model populated by the DOCX/PDF parsers."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ParseDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    element_id: str | None = None


class DocumentElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_id: str
    kind: Literal["heading", "paragraph", "table", "figure", "equation", "code", "unknown"]
    text: str = ""
    normalized_text: str = ""
    heading_level: int | None = Field(default=None, ge=1, le=9)
    heading_path: list[str] = Field(default_factory=list)
    page_number: int | None = Field(default=None, ge=1)
    source_index: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_format: Literal["docx", "pdf"]
    file_name: str
    elements: list[DocumentElement] = Field(default_factory=list)
    diagnostics: list[ParseDiagnostic] = Field(default_factory=list)
    page_count: int | None = Field(default=None, ge=1)
    parsing_complete: bool = False
    format_metadata: dict[str, Any] = Field(default_factory=dict)
