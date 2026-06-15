"""
Document Pydantic Schemas
Data validation and serialization for document endpoints
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class DocumentStatus(str, Enum):
    DRAFT = 'draft'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    EXPORTED = 'exported'


class SectionStatus(str, Enum):
    PENDING = 'pending'
    ASSIGNED = 'assigned'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    REVIEW = 'review'


class SectionType(str, Enum):
    TEXT = 'text'
    LIST = 'list'
    DIAGRAM = 'diagram'
    TABLE = 'table'


class AssignmentStrategy(str, Enum):
    HOST = 'host'
    ROLE = 'role'
    MANUAL = 'manual'
    AUTO = 'auto'


# ============================================================================
# Request Models
# ============================================================================

class CreateDocumentRequest(BaseModel):
    debate_id: str = Field(..., description="Debate ID to attach document to")
    template_id: str = Field(..., description="Template ID to use")
    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    custom_sections: Optional[List[Dict[str, Any]]] = Field(default=None, description="Override template sections")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()


class UpdateDocumentRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    status: Optional[DocumentStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class AssignSectionRequest(BaseModel):
    section_id: str = Field(..., description="Section ID to assign")
    agent_id: Optional[str] = Field(default=None, description="Agent ID to assign")
    agent_name: Optional[str] = Field(default=None, max_length=200, description="Agent name")

    @field_validator('agent_id', 'agent_name')
    @classmethod
    def validate_assignment(cls, v: Optional[str], info) -> Optional[str]:
        # At least one of agent_id or agent_name must be provided
        values = info.data
        if not v and not values.get('agent_id') and not values.get('agent_name'):
            raise ValueError('Either agent_id or agent_name must be provided')
        return v


class UpdateSectionRequest(BaseModel):
    status: Optional[SectionStatus] = None
    word_count: Optional[int] = Field(default=None, ge=0, description="Current word count")
    content: Optional[str] = Field(default=None, description="Section content")


# ============================================================================
# Response Models
# ============================================================================

class DocumentSectionResponse(BaseModel):
    section_id: str
    document_id: str
    section_key: str
    section_title: str
    section_type: SectionType
    section_order: int
    
    assigned_agent_id: Optional[str] = None
    assigned_agent_name: Optional[str] = None
    assignment_strategy: Optional[AssignmentStrategy] = None
    
    word_limit: Optional[int] = None
    word_count: int = 0
    status: SectionStatus
    
    content: Optional[str] = None  # THE MISSING FIELD!
    content_schema: Optional[Dict[str, Any]] = None
    
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentMetadataResponse(BaseModel):
    total_words: int = 0
    target_words: int = 0
    completion_percentage: int = 0
    last_edited_by: Optional[str] = None


class DocumentResponse(BaseModel):
    document_id: str
    debate_id: str
    template_id: str
    title: str
    status: DocumentStatus
    metadata: DocumentMetadataResponse
    sections: List[DocumentSectionResponse]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentListItem(BaseModel):
    document_id: str
    debate_id: str
    title: str
    status: DocumentStatus
    template_id: str
    completion_percentage: int = 0
    section_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: List[DocumentListItem]
    total: int
    has_more: bool = False
