from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl

Modality = Literal["audio", "light"]

class SourceDoc(BaseModel):
    id: str
    title: str
    year: Optional[int] = None
    url: Optional[HttpUrl] = None
    publisher: Optional[str] = None
    doc_type: Optional[str] = None
    provenance: Optional[str] = None

class DescriptorProxies(BaseModel):
    laeq_bucket_db: Optional[str] = None
    spectral_notes: Optional[str] = None
    tlm_freq_hz: Optional[str] = None
    tlm_mod_percent: Optional[str] = None
    notes: Optional[str] = None

class LegalEthicalTags(BaseModel):
    uncat: Optional[str] = None
    echr_article_3: Optional[str] = None
    istanbul_protocol_refs: Optional[List[str]] = None
    cases_cited: Optional[List[str]] = None

class Case(BaseModel):
    id: str
    title: str
    country: Optional[str] = None
    period: Optional[str] = None
    modalities: List[Modality]
    description: str
    reported_effects: List[str] = Field(default_factory=list)
    descriptors: DescriptorProxies = Field(default_factory=DescriptorProxies)
    legal_ethics: Optional[LegalEthicalTags] = None
    sources: List[SourceDoc] = Field(default_factory=list)
