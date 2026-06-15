from __future__ import annotations

from pydantic import BaseModel


class SynthesisCompletedPayload(BaseModel):
    text: str
    output_path: str
    sample_rate: int
