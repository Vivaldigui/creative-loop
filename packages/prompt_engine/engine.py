from __future__ import annotations

import difflib
import hashlib
from typing import Any

from pydantic import BaseModel


class PromptFields(BaseModel):
    # Core intent
    objective: str | None = None
    channel: str | None = None
    positioning: str | None = None

    # Product / audience
    product_name: str | None = None
    brand_name: str | None = None
    audience: str | None = None
    segment: str | None = None

    # Format / dimensions
    ad_format: str | None = None
    dimensions: str | None = None

    # Visual composition
    composition: str | None = None
    framing: str | None = None
    background: str | None = None
    lighting: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None

    # Typography / text
    typography: str | None = None
    exact_text: str | None = None      # verbatim text to appear in creative
    headline_text: str | None = None
    body_text: str | None = None
    cta_text: str | None = None
    margins: str | None = None

    # Placement / restrictions
    placement: str | None = None
    mandatory_elements: str | None = None
    authorized_references: str | None = None
    forbidden_elements: str | None = None
    forbidden_claims: str | None = None
    brand_restrictions: str | None = None
    policy_risks: str | None = None

    # Experiment traceability
    experiment_hypothesis: str | None = None
    primary_variable: str | None = None
    learnings_used: str | None = None
    known_limitations: str | None = None

    originality_note: str = "This is an original creative. Do not copy any third-party ad."


class VersionedPrompt(BaseModel):
    prompt_text: str
    structured_fields: dict[str, Any]
    version_number: int
    content_hash: str
    diff_summary: str | None = None
    change_reason: str | None = None


class PromptEngine:
    """
    Assembles and versions prompts.
    Never silently modifies — each change creates a new version.
    All fields are rendered in a deterministic, stable order so unified-diffs are readable.
    """

    # Ordered sections for deterministic rendering
    _SECTIONS: list[tuple[str, str]] = [
        ("objective", "OBJECTIVE"),
        ("channel", "CHANNEL"),
        ("positioning", "POSITIONING"),
        ("product_name", "PRODUCT"),
        ("brand_name", "BRAND"),
        ("audience", "TARGET AUDIENCE"),
        ("segment", "SEGMENT"),
        ("ad_format", "FORMAT"),
        ("dimensions", "DIMENSIONS"),
        ("composition", "COMPOSITION"),
        ("framing", "FRAMING"),
        ("background", "BACKGROUND"),
        ("lighting", "LIGHTING"),
        ("primary_color", "PRIMARY COLOR"),
        ("secondary_color", "SECONDARY COLOR"),
        ("typography", "TYPOGRAPHY"),
        ("exact_text", "EXACT TEXT"),
        ("headline_text", "HEADLINE"),
        ("body_text", "BODY TEXT"),
        ("cta_text", "CTA"),
        ("margins", "MARGINS"),
        ("placement", "PLACEMENT"),
        ("mandatory_elements", "MANDATORY ELEMENTS"),
        ("authorized_references", "AUTHORIZED REFERENCES"),
        ("forbidden_elements", "DO NOT INCLUDE"),
        ("forbidden_claims", "FORBIDDEN CLAIMS"),
        ("brand_restrictions", "BRAND RESTRICTIONS"),
        ("policy_risks", "POLICY RISKS"),
        ("experiment_hypothesis", "EXPERIMENT HYPOTHESIS"),
        ("primary_variable", "PRIMARY TEST VARIABLE"),
        ("learnings_used", "LEARNINGS APPLIED"),
        ("known_limitations", "KNOWN LIMITATIONS"),
        ("originality_note", "NOTE"),
    ]

    def build(self, fields: PromptFields) -> str:
        parts: list[str] = []
        for attr, label in self._SECTIONS:
            value = getattr(fields, attr, None)
            if value:
                parts.append(f"{label}: {value}")
        return "\n".join(parts)

    def content_hash(self, prompt_text: str) -> str:
        return hashlib.sha256(prompt_text.encode()).hexdigest()

    def diff(self, old_text: str, new_text: str) -> str:
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                old_lines, new_lines, fromfile="v_prev", tofile="v_new", lineterm=""
            )
        )

    def new_version(
        self,
        fields: PromptFields,
        parent_text: str | None,
        parent_version: int,
        change_reason: str,
    ) -> VersionedPrompt:
        new_text = self.build(fields)
        diff_summary = self.diff(parent_text or "", new_text) if parent_text else None
        chash = self.content_hash(new_text)
        return VersionedPrompt(
            prompt_text=new_text,
            structured_fields=fields.model_dump(exclude_none=True),
            version_number=parent_version + 1,
            content_hash=chash,
            diff_summary=diff_summary,
            change_reason=change_reason,
        )
