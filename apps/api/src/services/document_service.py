"""
Document Service
Business logic for document CRUD operations
"""
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import psycopg2.extras

from ..database import get_db_connection, get_cursor
from ..schemas.documents import (
    DocumentStatus, SectionStatus, SectionType, AssignmentStrategy
)

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for managing documents and sections"""
    
    def create_document(
        self,
        debate_id: str,
        template_id: str,
        title: str,
        template_sections: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new document for a debate
        
        Args:
            debate_id: UUID of the debate
            template_id: ID of the template to use
            title: Document title
            template_sections: List of section definitions from template
            metadata: Optional metadata dict
            
        Returns:
            Created document with sections
            
        Raises:
            ValueError: If debate doesn't exist or validation fails
            psycopg2.Error: Database errors
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Verify debate exists
            cursor.execute(
                "SELECT debate_id FROM debates WHERE debate_id = %s",
                (debate_id,)
            )
            if not cursor.fetchone():
                raise ValueError(f"Debate {debate_id} not found")
            
            # Check if document already exists for this debate
            cursor.execute(
                "SELECT document_id FROM documents WHERE debate_id = %s",
                (debate_id,)
            )
            existing = cursor.fetchone()
            if existing:
                raise ValueError(f"Document already exists for debate {debate_id}")
            
            # Create document
            document_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO documents (
                    document_id, debate_id, template_id, title, 
                    status, metadata, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING document_id
            """, (
                document_id,
                debate_id,
                template_id,
                title,
                DocumentStatus.DRAFT.value,
                psycopg2.extras.Json(metadata or {}),
                datetime.now(timezone.utc),
                datetime.now(timezone.utc)
            ))
            
            # Create sections
            for section in template_sections:
                section_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO document_sections (
                        section_id, document_id, section_key, section_title,
                        section_type, section_order, assignment_strategy,
                        word_limit, status, content_schema, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    section_id,
                    document_id,
                    section['key'],
                    section['title'],
                    section.get('type', 'text'),
                    section.get('order', 0),
                    section.get('assignmentStrategy'),
                    section.get('wordLimit'),
                    SectionStatus.PENDING.value,
                    psycopg2.extras.Json(section.get('schema')) if section.get('schema') else None,
                    datetime.now(timezone.utc)
                ))
            
            conn.commit()
            
            return self.get_document(document_id)
    
    def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get document with all sections
        
        Raises:
            ValueError: If document not found
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Get document
            cursor.execute("""
                SELECT document_id, debate_id, template_id, title,
                       status, metadata, created_at, updated_at, completed_at
                FROM documents
                WHERE document_id = %s
            """, (document_id,))
            
            doc_row = cursor.fetchone()
            if not doc_row:
                raise ValueError(f"Document {document_id} not found")
            
            # Get sections (including content!)
            cursor.execute("""
                SELECT section_id, document_id, section_key, section_title,
                       section_type, section_order, assigned_agent_id, assigned_agent_name,
                       assignment_strategy, word_limit, word_count, status,
                       content, content_schema, created_at, started_at, completed_at, updated_at
                FROM document_sections
                WHERE document_id = %s
                ORDER BY section_order ASC
            """, (document_id,))
            
            sections = [dict(row) for row in cursor.fetchall()]
            
            # DEBUG: Check if content is in sections
            print(f"\n📋 DEBUG get_document sections:")
            for idx, s in enumerate(sections):
                has_content = 'content' in s and s['content'] is not None
                content_len = len(s.get('content', '')) if has_content else 0
                print(f"  Section {idx}: {s.get('section_title')} - content: {has_content} ({content_len} chars)")
            print()
            
            # Calculate metadata
            total_words = sum(s['word_count'] for s in sections)
            target_words = sum(s['word_limit'] or 0 for s in sections)
            completed_count = sum(1 for s in sections if s['status'] == 'completed')
            completion_pct = int((completed_count / len(sections) * 100)) if sections else 0
            
            return {
                'document_id': doc_row['document_id'],
                'debate_id': doc_row['debate_id'],
                'template_id': doc_row['template_id'],
                'title': doc_row['title'],
                'status': doc_row['status'],
                'metadata': {
                    'total_words': total_words,
                    'target_words': target_words,
                    'completion_percentage': completion_pct,
                    **doc_row['metadata']
                },
                'sections': sections,
                'created_at': doc_row['created_at'].isoformat(),
                'updated_at': doc_row['updated_at'].isoformat(),
                'completed_at': doc_row['completed_at'].isoformat() if doc_row['completed_at'] else None,
            }
    
    def update_document(
        self,
        document_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update document fields"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Build update query dynamically
            updates = []
            params = []
            
            if title is not None:
                updates.append("title = %s")
                params.append(title)
            
            if status is not None:
                # Validate status transition
                self._validate_status_transition(cursor, document_id, status)
                updates.append("status = %s")
                params.append(status)
                
                if status == DocumentStatus.COMPLETED.value:
                    updates.append("completed_at = %s")
                    params.append(datetime.now(timezone.utc))
            
            if metadata is not None:
                updates.append("metadata = %s")
                params.append(psycopg2.extras.Json(metadata))
            
            if not updates:
                return self.get_document(document_id)
            
            params.append(document_id)
            query = f"""
                UPDATE documents
                SET {', '.join(updates)}
                WHERE document_id = %s
            """
            
            cursor.execute(query, params)
            conn.commit()
            
            return self.get_document(document_id)
    
    def assign_section(
        self,
        section_id: str,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assign a section to an agent"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Verify section exists
            cursor.execute(
                "SELECT document_id, status FROM document_sections WHERE section_id = %s",
                (section_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Section {section_id} not found")
            
            document_id = row['document_id']
            
            # Update assignment
            cursor.execute("""
                UPDATE document_sections
                SET assigned_agent_id = %s,
                    assigned_agent_name = %s,
                    status = CASE 
                        WHEN status = 'pending' THEN 'assigned'
                        ELSE status
                    END
                WHERE section_id = %s
            """, (agent_id, agent_name, section_id))
            
            conn.commit()
            
            return self.get_document(document_id)
    
    def update_section_progress(
        self,
        section_id: str,
        word_count: Optional[int] = None,
        status: Optional[str] = None
    ) -> None:
        """Update section progress (word count, status)"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            updates = []
            params = []
            
            if word_count is not None:
                updates.append("word_count = %s")
                params.append(word_count)
            
            if status is not None:
                updates.append("status = %s")
                params.append(status)
                
                if status == SectionStatus.IN_PROGRESS.value:
                    updates.append("started_at = COALESCE(started_at, %s)")
                    params.append(datetime.now(timezone.utc))
                elif status == SectionStatus.COMPLETED.value:
                    updates.append("completed_at = %s")
                    params.append(datetime.now(timezone.utc))
            
            if not updates:
                return
            
            params.append(section_id)
            query = f"""
                UPDATE document_sections
                SET {', '.join(updates)}
                WHERE section_id = %s
            """
            
            cursor.execute(query, params)
            conn.commit()
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document (CASCADE deletes sections)"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            cursor.execute(
                "DELETE FROM documents WHERE document_id = %s",
                (document_id,)
            )
            
            deleted = cursor.rowcount > 0
            conn.commit()
            
            return deleted
    
    # ========================================================================
    # Private Helpers
    # ========================================================================
    
    def _validate_status_transition(
        self,
        cursor,
        document_id: str,
        new_status: str
    ) -> None:
        """Validate document status transition"""
        cursor.execute(
            "SELECT status FROM documents WHERE document_id = %s",
            (document_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Document {document_id} not found")
        
        current_status = row['status']
        
        # Define valid transitions
        valid_transitions = {
            'draft': ['in_progress'],
            'in_progress': ['completed', 'draft'],
            'completed': ['exported'],
            'exported': [],  # Terminal state
        }
        
        if new_status not in valid_transitions.get(current_status, []):
            raise ValueError(
                f"Invalid status transition: {current_status} -> {new_status}"
            )
