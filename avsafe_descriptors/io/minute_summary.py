from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class MinuteSummary(BaseModel):
    timestamp_utc: datetime = Field(..., description="Minute boundary in UTC")
    laeq_db: Optional[float] = Field(default=None, description="A-weighted LAeq (1-min)")
    lcpeak_db: Optional[float] = None
    one_third_octave_db: Optional[List[float]] = None
    one_third_octave_centers_hz: Optional[List[float]] = None
    bands_a_weighted: Optional[bool] = None

    tlm_f_dom_hz: Optional[float] = None
    tlm_percent_mod: Optional[float] = None
    tlm_flicker_index: Optional[float] = None

    prev_hash: Optional[str] = Field(default=None)
    signature: Optional[str] = Field(default=None)

    class Config:
        extra = "forbid"
