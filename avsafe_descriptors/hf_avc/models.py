#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
HF-AVC data models (Pydantic v2)

Covers the v2 case structure used by case_template_v1.json:
- Jurisdiction, Period
- Descriptors (Audio/Light) with value/range+confidence pattern
- Standards mapping (WHO 2018, IEEE 1789)
- Legal/Ethics, Sources, Provenance, Privacy, Links
- Case root model

Design goals:
- Professional, well-typed, and documented
- Gentle normalization (e.g., ISO-2 uppercase; modality tokens lowercase)
- Minimal constraints (accept legacy/unknown fields; extra="ignore")
- Safe defaults (no mutable default args)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Literal, Any
from enum import Enum
import re

from pydantic import BaseModel, Field, AnyUrl, field_validator, model_validator, ConfigDict


# ---------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------

class Range(BaseModel):
    """Numeric closed interval."""
    model_config = ConfigDict(extra='ignore')
    min: Optional[float] = Field(default=None)
    max: Optional[float] = Field(default=None)

    @model_validator(mode="after")
    def _check_order(self) -> "Range":
        if self.min is not None and self.max is not None and self.min > self.max:
            # Swap rather than fail (gentle fix)
            self.min, self.max = self.max, self.min
        return self


class Metric(BaseModel):
    """
    Measurement value OR range + optional confidence and unit.
    Examples:
      {"value": 60.0, "confidence": 0.6}
      {"range": {"min": 55, "max": 70}, "confidence": 0.6}
    """
    model_config = ConfigDict(extra='ignore')
    value: Optional[float] = None
    range: Optional[Range] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    unit: Optional[str] = None  # e.g., 'unit:DeciBelA', 'unit:HZ', 'unit:PERCENT'

    @model_validator(mode="after")
    def _ensure_value_or_range(self) -> "Metric":
        if self.value is None and self.range is None:
            # Accept empty metric; caller may treat as unknown
            return self
        return self


# ---------------------------------------------------------------------
# Domain enums (kept permissive; we normalize but don’t hard-fail)
# ---------------------------------------------------------------------

class Modality(str, Enum):
    audio = "audio"
    light = "light"


# ---------------------------------------------------------------------
# Descriptor groups
# ---------------------------------------------------------------------

class AudioModulation(BaseModel):
    """Optional modulation descriptors (non-speech)."""
    model_config = ConfigDict(extra='ignore')
    repetition_index: Optional[float] = None
    roughness_index: Optional[float] = None
    notes: Optional[str] = None


class AudioDescriptor(BaseModel):
    """Audio metrics (A-weighted LAeq, C-peak, 1/3-octave, modulation)."""
    model_config = ConfigDict(extra='ignore')

    laeq_db: Optional[Metric] = None
    lcpeak_db: Optional[Metric] = None

    # third-octave levels: {"125": 60.0, "250": 58.5, ...}
    third_octave_db: Dict[str, float] = Field(default_factory=dict)

    modulation: Optional[AudioModulation] = None

    @field_validator("third_octave_db", mode="before")
    @classmethod
    def _normalize_third_octave_keys(cls, v: Any) -> Dict[str, float]:
        """
        Accept numeric or string keys; coerce to canonical string (no trailing .0).
        Allow wide band range (10–40000 Hz). Values kept as float.
        """
        if v is None:
            return {}
        out: Dict[str, float] = {}
        for k, val in dict(v).items():
            try:
                f = float(k)
                if not (10.0 <= f <= 40000.0):
                    # Keep but don’t fail; downstream can filter
                    pass
                # Format key without unnecessary decimals (e.g., "125")
                key = str(int(f)) if abs(f - int(f)) < 1e-9 else str(f)
                out[key] = float(val)
            except Exception:
                # Ignore unparseable keys silently
                continue
        return out


class LightDescriptor(BaseModel):
    """Lighting (TLM/flicker) metrics."""
    model_config = ConfigDict(extra='ignore')

    tlm_freq_hz: Optional[Metric] = None          # frequency (Hz)
    tlm_mod_percent: Optional[Metric] = None      # percent modulation
    flicker_index: Optional[Metric] = None        # flicker index (0–1)


class Descriptors(BaseModel):
    """Top-level descriptor bundle for a case."""
    model_config = ConfigDict(extra='ignore')

    audio: Optional[AudioDescriptor] = None
    light: Optional[LightDescriptor] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------
# Context, period, mapping, legal/ethics
# ---------------------------------------------------------------------

class Coordinates(BaseModel):
    model_config = ConfigDict(extra='ignore')
    lat: Optional[float] = None
    lon: Optional[float] = None


class Jurisdiction(BaseModel):
    model_config = ConfigDict(extra='ignore')
    country_iso2: Optional[str] = None   # 'US', 'DE', ...
    place: Optional[str] = None
    coordinates: Optional[Coordinates] = None

    @field_validator("country_iso2")
    @classmethod
    def _norm_iso2(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", v):
            # Don’t fail; keep raw token
            return v
        return v


class Period(BaseModel):
    """
    Textual dates for flexibility (YYYY or YYYY-MM or YYYY-MM-DD).
    Keep as strings to preserve archival uncertainty and partial dates.
    """
    model_config = ConfigDict(extra='ignore')
    start: Optional[str] = None
    end: Optional[str] = None

    _RE_YEAR = re.compile(r"^\d{4}$")
    _RE_YM = re.compile(r"^\d{4}-\d{2}$")
    _RE_YMD = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("start", "end")
    @classmethod
    def _validate_partial_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if cls._RE_YEAR.fullmatch(v) or cls._RE_YM.fullmatch(v) or cls._RE_YMD.fullmatch(v):
            return v
        # keep unvalidated token (e.g., '1993-early'); downstream can decide
        return v


class WHO_2018_Map(BaseModel):
    model_config = ConfigDict(extra='ignore')
    night_guideline_db: Optional[float] = None
    likely_exceeded: Optional[bool] = None
    basis: Optional[str] = None


class IEEE_1789_Map(BaseModel):
    model_config = ConfigDict(extra='ignore')
    zone: Optional[str] = None  # e.g., "NOEL", "low-risk", "unknown"
    notes: Optional[str] = None


class StandardsMapping(BaseModel):
    model_config = ConfigDict(extra='ignore')
    who_noise_2018: Optional[WHO_2018_Map] = None
    ieee_1789_2015: Optional[IEEE_1789_Map] = None


class LegalEthics(BaseModel):
    model_config = ConfigDict(extra='ignore')
    uncat: Optional[str] = None
    echr_article_3: Optional[str] = None
    istanbul_protocol_refs: List[str] = Field(default_factory=list)
    cases_cited: List[str] = Field(default_factory=list)


class Source(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    title: str
    year: Optional[int] = None
    url: Optional[AnyUrl] = None
    publisher: Optional[str] = None
    doc_type: Optional[str] = None
    provenance: Optional[str] = None
    pages: Optional[str] = None
    quote: Optional[str] = None
    accessed: Optional[str] = None          # ISO date preferred
    reliability: Optional[str] = None       # 'low' | 'medium' | 'high' (free text accepted)


class Provenance(BaseModel):
    model_config = ConfigDict(extra='ignore')
    coded_by: List[str] = Field(default_factory=list)
    double_coded_by: List[str] = Field(default_factory=list)
    adjudicator: Optional[str] = None
    coding_date: Optional[str] = None       # ISO date
    review_status: Optional[str] = None     # e.g., 'external_pending'
    interrater_kappa: Optional[float] = None
    notes: Optional[str] = None


class Privacy(BaseModel):
    model_config = ConfigDict(extra='ignore')
    sensitivity: Optional[str] = None       # e.g., 'low'|'medium'|'high'
    redactions: List[str] = Field(default_factory=list)


class Links(BaseModel):
    model_config = ConfigDict(extra='ignore')
    related_cases: List[str] = Field(default_factory=list)
    media: List[AnyUrl] = Field(default_factory=list)


# ---------------------------------------------------------------------
# Root: Case
# ---------------------------------------------------------------------

class Case(BaseModel):
    """
    Root HF-AVC case record.
    Matches case_template_v1.json and the JSON Schema (case_schema_v1.json).
    """
    model_config = ConfigDict(extra='ignore')

    # Metadata
    schema_version: str = Field(default="1.0.0")
    id: str
    title: str

    # JSON-LD-friendly bits (optional)
    # @context and @type are ignored if present (extra='ignore')

    # Context
    jurisdiction: Optional[Jurisdiction] = None
    period: Optional[Period] = None

    coercion_context: List[str] = Field(default_factory=list)
    modalities: List[str] = Field(default_factory=list)

    summary: Optional[str] = None

    exposure_pattern: Optional[Dict[str, Any]] = None  # flexible; validated downstream
    reported_effects: List[str] = Field(default_factory=list)

    descriptors: Optional[Descriptors] = None
    standards_mapping: Optional[StandardsMapping] = None
    legal_ethics: Optional[LegalEthics] = None

    sources: List[Source] = Field(default_factory=list)
    provenance: Optional[Provenance] = None

    privacy: Optional[Privacy] = None
    links: Optional[Links] = None

    # ---- Normalizers -------------------------------------------------

    @field_validator("modalities", mode="before")
    @classmethod
    def _norm_modalities(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        # lowercase, dedupe, preserve order
        seen = set()
        out: List[str] = []
        for tok in v:
            if not isinstance(tok, str):
                continue
            t = tok.strip().lower()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    @field_validator("coercion_context", mode="before")
    @classmethod
    def _norm_context(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        seen = set()
        out: List[str] = []
        for tok in v:
            if not isinstance(tok, str):
                continue
            t = tok.strip().lower()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    # ---- Convenience --------------------------------------------------

    def modality_has(self, name: Literal["audio", "light"]) -> bool:
        return name in self.modalities

    def who_likely_exceeded(self) -> Optional[bool]:
        if self.standards_mapping and self.standards_mapping.who_noise_2018:
            return self.standards_mapping.who_noise_2018.likely_exceeded
        return None

    def ieee_zone(self) -> Optional[str]:
        if self.standards_mapping and self.standards_mapping.ieee_1789_2015:
            return self.standards_mapping.ieee_1789_2015.zone
        return None


# ---------------------------------------------------------------------
# Corpus wrapper (optional)
# ---------------------------------------------------------------------

class Corpus(BaseModel):
    """Simple container for bulk interchange."""
    model_config = ConfigDict(extra='ignore')
    cases: List[Case] = Field(default_factory=list)


__all__ = [
    "Range", "Metric",
    "AudioModulation", "AudioDescriptor", "LightDescriptor", "Descriptors",
    "Coordinates", "Jurisdiction", "Period",
    "WHO_2018_Map", "IEEE_1789_Map", "StandardsMapping",
    "LegalEthics", "Source", "Provenance", "Privacy", "Links",
    "Case", "Corpus",
]
