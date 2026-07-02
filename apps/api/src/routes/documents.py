"""
Document API Routes
REST endpoints for document management
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, Dict, Any

from ..auth import get_current_user, check_workspace_access
from ..services.document_service import DocumentService
from ..schemas.documents import (
    CreateDocumentRequest,
    UpdateDocumentRequest,
    AssignSectionRequest,
    UpdateSectionRequest,
    DocumentResponse,
    DocumentListResponse,
)

router = APIRouter()


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    request: CreateDocumentRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Create a new document for a debate
    
    Requires:
    - Valid debate_id
    - Valid template_id
    - User has access to workspace
    """
    service = DocumentService()
    
    try:
        # Verify workspace access (get debate first)
        from ..debate_service import DebateService
        debate_service = DebateService()
        debate = debate_service.get_debate(request.debate_id)
        
        if not debate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Debate {request.debate_id} not found"
            )
        
        # Check workspace access
        if current_user:
            check_workspace_access(current_user, debate['workspace_id'])
        
        # Validate that custom_sections is provided
        if not request.custom_sections:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="custom_sections is required (client should send template sections)"
            )
        
        template_sections = request.custom_sections
        
        document = service.create_document(
            debate_id=request.debate_id,
            template_id=request.template_id,
            title=request.title,
            template_sections=template_sections,
            metadata={'template_id': request.template_id}
        )

        # Assign sections so agents/host actually write to them (previously
        # sections were created unassigned → nothing ever populated them):
        #   HOST-strategy → the Review Chair (the host lives in policy_config,
        #                   not as a participant, so it can't be "found")
        #   otherwise     → round-robin across the panel, by name
        try:
            from ..database import get_db_connection, get_cursor
            doc_id = document['document_id']
            with get_db_connection() as conn:
                cur = get_cursor(conn)
                cur.execute(
                    "SELECT agent_config, role_name FROM participants WHERE debate_id = %s ORDER BY created_at ASC",
                    (request.debate_id,),
                )
                names = [((p['agent_config'] or {}).get('name') or p['role_name']) for p in cur.fetchall()]
                names = [n for n in names if n and n != 'Ultimate Host']
                cur.execute(
                    "SELECT section_id, assignment_strategy FROM document_sections WHERE document_id = %s ORDER BY section_order",
                    (doc_id,),
                )
                secs = cur.fetchall()
            auto_idx = 0
            for s in secs:
                strat = (s.get('assignment_strategy') or 'auto').lower()
                if strat == 'host':
                    service.assign_section(section_id=str(s['section_id']), agent_name='Review Chair')
                elif names:
                    service.assign_section(section_id=str(s['section_id']), agent_name=names[auto_idx % len(names)])
                    auto_idx += 1
            document = service.get_document(doc_id)
        except Exception as _assign_exc:
            print(f"⚠️ Document section auto-assignment failed (non-fatal): {_assign_exc}")

        return DocumentResponse(**document)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document: {str(e)}"
        )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get document by ID with all sections"""
    service = DocumentService()
    
    try:
        document = service.get_document(document_id)
        
        # Verify workspace access
        if current_user:
            from ..debate_service import DebateService
            debate_service = DebateService()
            debate = debate_service.get_debate(document['debate_id'])
            check_workspace_access(current_user, debate['workspace_id'])
        
        return DocumentResponse(**document)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}"
        )


@router.put("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    request: UpdateDocumentRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Update document metadata, title, or status"""
    service = DocumentService()
    
    try:
        # Get document first to verify access
        document = service.get_document(document_id)
        
        if current_user:
            from ..debate_service import DebateService
            debate_service = DebateService()
            debate = debate_service.get_debate(document['debate_id'])
            check_workspace_access(current_user, debate['workspace_id'])
        
        # Update document
        updated = service.update_document(
            document_id=document_id,
            title=request.title,
            status=request.status.value if request.status else None,
            metadata=request.metadata
        )
        
        return DocumentResponse(**updated)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document: {str(e)}"
        )


@router.post("/documents/{document_id}/sections/{section_id}/assign", response_model=DocumentResponse)
async def assign_section(
    document_id: str,
    section_id: str,
    request: AssignSectionRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Assign a section to an agent"""
    service = DocumentService()
    
    try:
        # Verify access
        document = service.get_document(document_id)
        
        if current_user:
            from ..debate_service import DebateService
            debate_service = DebateService()
            debate = debate_service.get_debate(document['debate_id'])
            check_workspace_access(current_user, debate['workspace_id'])
        
        # Assign section
        updated = service.assign_section(
            section_id=section_id,
            agent_id=request.agent_id,
            agent_name=request.agent_name
        )
        
        return DocumentResponse(**updated)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign section: {str(e)}"
        )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Delete a document"""
    service = DocumentService()
    
    try:
        # Verify access before deleting
        document = service.get_document(document_id)
        
        if current_user:
            from ..debate_service import DebateService
            debate_service = DebateService()
            debate = debate_service.get_debate(document['debate_id'])
            check_workspace_access(current_user, debate['workspace_id'])
        
        # Delete
        deleted = service.delete_document(document_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.get("/debates/{debate_id}/document", response_model=DocumentResponse)
async def get_debate_document(
    debate_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get document for a specific debate"""
    try:
        # Verify debate access
        from ..debate_service import DebateService
        debate_service = DebateService()
        debate = debate_service.get_debate(debate_id)
        
        if not debate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Debate {debate_id} not found"
            )
        
        if current_user:
            check_workspace_access(current_user, debate['workspace_id'])
        
        # Find document
        from ..database import get_db_connection, get_cursor
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute(
                "SELECT document_id FROM documents WHERE debate_id = %s",
                (debate_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No document found for debate {debate_id}"
                )
            
            service = DocumentService()
            document = service.get_document(row['document_id'])
            
            return DocumentResponse(**document)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get debate document: {str(e)}"
        )
