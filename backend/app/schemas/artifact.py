from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ArtifactDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: str
    project_id: str
    report_id: str
    artifact_type: str  # "PDF_REPORT", "SPREADSHEET", "VOICE_MEMO", "IMAGE"
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    storage_bucket: str
    storage_key: str
    uploaded_by: str
    uploaded_at: datetime
    extraction_status: str
    error_message: Optional[str] = None


class ArtifactUploadResponse(BaseModel):
    artifact: ArtifactDTO
    is_duplicate: bool = False
    message: str


class PresignedUrlResponse(BaseModel):
    artifact_id: str
    url: str
    expires_in_seconds: int = 900
