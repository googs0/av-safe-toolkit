
from __future__ import annotations
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any

class Source(BaseModel):
    id: str
    title: str
    year: int
    url: Optional[HttpUrl] = None
    publisher: Optional[str] = None
    doc_type: Optional[str] = None
    provenance: Optional[str] = None

class LegalEthics(BaseModel):
    uncat: Optional[str] = None
    echr_article_3: Optional[str] = None
    istanbul_protocol_refs: List[str] = []
    cases_cited: List[str] = []

class Descriptors(BaseModel):
    laeq_bucket_db: Optional[str] = None
    spectral_notes: Optional[str] = None
    tlm_freq_hz: Optional[str] = None
    tlm_mod_percent: Optional[str] = None
    notes: Optional[str] = None

class Case(BaseModel):
    id: str
    title: str
    country: Optional[str] = None
    period: Optional[str] = None
    modalities: List[str] = []
    description: Optional[str] = None
    reported_effects: List[str] = []
    descriptors: Descriptors = Field(default_factory=Descriptors)
    legal_ethics: LegalEthics = Field(default_factory=LegalEthics)
    sources: List[Source] = []

class Corpus(BaseModel):
    cases: List[Case]
