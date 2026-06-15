"""
Pydantic schemas for Memory Import endpoints
"""

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


# Importable sources list response
class ImportableDebate(BaseModel):
    """A debate that can be imported as memory source"""
    debate_id: str
    title: str
    state: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    chunk_count: int = Field(description="Total chunks available (materials + agent knowledge)")
    material_count: int = Field(description="Number of materials attached")
    artifact_count: int = Field(description="Number of artifacts created")
    participant_count: int = Field(description="Number of participants")


class ImportableSourcesResponse(BaseModel):
    """Response for GET /workspaces/{id}/memory/importable"""
    workspace_id: str
    debates: List[ImportableDebate]
    total_count: int


# Preview response
class MemoryPreviewChunk(BaseModel):
    """Preview of what chunks would be imported"""
    source_type: str  # 'material', 'agent_knowledge', 'artifact'
    title: str
    chunk_count: int
    last_updated: datetime


class MemoryPreviewResponse(BaseModel):
    """Response for GET /debates/{id}/memory/preview"""
    source_debate_id: str
    source_title: str
    total_chunks: int
    breakdown: List[MemoryPreviewChunk]
    date_range: dict  # {start, end}


# Import request
class MemoryImportRequest(BaseModel):
    """Request body for POST /debates/{id}/memory/import"""
    source_debate_ids: List[str] = Field(min_length=1, description="Debate IDs to import from")
    source_type: Literal['debate_full', 'materials_only'] = Field(
        default='debate_full',
        description="What to import: all chunks or just materials"
    )
    scope: Literal['all_agents', 'specific_agents'] = Field(
        default='all_agents',
        description="Who can access: all participants or selected ones"
    )
    participant_ids: Optional[List[str]] = Field(
        default=None,
        description="Required if scope='specific_agents'"
    )
    metadata: Optional[dict] = Field(default_factory=dict, description="Import context")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_debate_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                "source_type": "debate_full",
                "scope": "all_agents",
                "metadata": {"reason": "Import Q1 strategy for context"}
            }
        }
    )


class MemoryImportResponse(BaseModel):
    """Response for POST /debates/{id}/memory/import"""
    debate_id: str
    grants_created: int
    grant_ids: List[str]


# Grant listing response
class MemoryGrant(BaseModel):
    """A single memory grant"""
    grant_id: str
    source_debate_id: Optional[str] = None
    source_debate_title: Optional[str] = None
    source_artifact_id: Optional[str] = None
    source_artifact_title: Optional[str] = None
    source_type: str
    scope: str
    allowed_participant_ids: Optional[List[str]] = None
    granted_by: str
    granted_at: datetime
    expires_at: Optional[datetime] = None
    metadata: dict


class MemoryGrantsResponse(BaseModel):
    """Response for GET /debates/{id}/memory/grants"""
    debate_id: str
    grants: List[MemoryGrant]
    total_count: int


# Retrieval request (internal/service use)
class MemoryRetrievalRequest(BaseModel):
    """Request for retrieve_allowed_chunks service function"""
    debate_id: str
    participant_id: Optional[str] = None  # If None, retrieve for all
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    retrieval_method: Literal['keyword', 'vector'] = Field(default='keyword')


class MemoryChunkResult(BaseModel):
    """A single chunk result from retrieval"""
    chunk_id: str
    chunk_text: str
    source_debate_id: Optional[str] = None
    source_material_id: Optional[str] = None
    agent_id: Optional[str] = None
    chunk_metadata: dict
    score: float  # Relevance score


class MemoryRetrievalResponse(BaseModel):
    """Response from retrieve_allowed_chunks"""
    debate_id: str
    participant_id: Optional[str] = None
    query: str
    chunks: List[MemoryChunkResult]
    total_chunks: int
    grant_ids_used: List[str] = Field(default_factory=list, description="Grants that allowed retrieval")
    retrieval_method: str
