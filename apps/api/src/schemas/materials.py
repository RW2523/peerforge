"""
Pydantic schemas for materials endpoints
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class MaterialUploadResponse(BaseModel):
    """Response after uploading materials"""
    material_ids: List[str] = Field(..., description="UUIDs of created materials")
    job_ids: List[str] = Field(..., description="Celery task IDs for processing jobs")
    total_files: int = Field(..., description="Number of files uploaded")


class MaterialStatus(BaseModel):
    """Status of a single material"""
    material_id: str
    title: str
    kind: str  # 'file', 'audio', 'text', 'link', 'file_placeholder'
    material_category: str = 'supplementary'  # main_research | research | transcript | supplementary
    is_primary: bool = False
    file_size_bytes: Optional[int] = None
    file_mime_type: Optional[str] = None
    processed_status: str  # 'pending', 'processing', 'complete', 'failed', 'needs_ocr'
    processing_metadata: Dict = Field(default_factory=dict)
    created_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None


class MaterialsStatusResponse(BaseModel):
    """Status of all materials in a debate"""
    debate_id: str
    total_materials: int
    status_summary: Dict[str, int]  # {'complete': 5, 'processing': 2, 'failed': 1}
    materials: List[MaterialStatus]


class MaterialRetryRequest(BaseModel):
    """Request to retry failed material processing"""
    material_id: str


class MaterialRetryResponse(BaseModel):
    """Response after retrying material"""
    material_id: str
    job_id: str
    message: str
