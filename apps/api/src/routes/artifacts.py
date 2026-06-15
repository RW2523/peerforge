"""
Live Artifacts API Routes (V1)
Reference: docs/design/LIVE-ARTIFACTS-TECHNICAL-SPEC.md
"""
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
import psycopg2.extras

import psycopg2
from ..config import settings

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class SectionAssignment(BaseModel):
    section_id: str = Field(..., description="Section key from template")
    participant_id: str = Field(..., description="Owner participant ID")


class ArtifactInitRequest(BaseModel):
    template_id: str = Field(..., description="Template ID (e.g., 'prd', 'brief')")
    title: Optional[str] = Field(None, description="Custom artifact title (defaults to template title)")
    section_assignments: List[SectionAssignment] = Field(..., description="Section ownership assignments")


class SectionInfo(BaseModel):
    section_id: str
    title: str
    owner_participant_id: Optional[str]
    status: str  # drafting, committed, locked
    content: str
    word_count: int
    citations: List[dict]
    block_type: str  # rich_text, chart, table, diagram_mermaid


class ArtifactInitResponse(BaseModel):
    artifact_id: str
    debate_id: str
    template_id: str
    title: str
    version: int
    status: str
    sections: List[SectionInfo]
    created_at: str


class ArtifactGetResponse(BaseModel):
    artifact_id: str
    debate_id: str
    template_id: str
    title: str
    version: int
    status: str
    sections: List[SectionInfo]
    quality_report: Optional[dict]
    created_at: str
    updated_at: str
    finalized_at: Optional[str]


class SectionEventRequest(BaseModel):
    event_type: str = Field(..., description="append, replace, typing (ephemeral)")
    content: str = Field(..., description="Markdown content or JSON payload for charts/tables")
    citations: Optional[List[dict]] = Field(default_factory=list, description="Citations for this content")


class SectionEventResponse(BaseModel):
    event_id: str
    section_id: str
    artifact_id: str
    event_type: str
    actor_participant_id: str
    content_preview: str
    created_at: str


class ArtifactEvent(BaseModel):
    event_id: str
    artifact_id: str
    section_id: Optional[str]
    event_type: str
    actor_participant_id: Optional[str]
    payload: dict
    created_at: str


class ArtifactEventsResponse(BaseModel):
    events: List[ArtifactEvent]
    next_cursor: Optional[str]


# ============================================================================
# Helper Functions
# ============================================================================

def get_auth_context(authorization: Optional[str] = Header(None)):
    """
    Extract user/workspace from JWT. For demo purposes, returns default workspace.
    In production, validate JWT and extract user_id + workspace_id from claims.
    """
    # TODO: Real JWT validation when REQUIRE_AUTH=true
    return {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "workspace_id": "00000000-0000-0000-0000-000000000101"
    }


def verify_debate_access(debate_id: str, workspace_id: str, conn) -> dict:
    """Verify debate exists and belongs to workspace"""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT debate_id, workspace_id, state, title
            FROM debates
            WHERE debate_id = %s AND workspace_id = %s
        """, (debate_id, workspace_id))
        debate = cur.fetchone()
        if not debate:
            raise HTTPException(status_code=404, detail="Debate not found or access denied")
        return dict(debate)


def verify_participant_in_debate(participant_id: str, debate_id: str, conn) -> dict:
    """Verify participant exists in this debate"""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT participant_id, agent_config
            FROM participants
            WHERE participant_id = %s AND debate_id = %s
        """, (participant_id, debate_id))
        participant = cur.fetchone()
        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found in this debate")
        return dict(participant)


def get_artifact_sections(artifact_id: str, conn) -> List[dict]:
    """Retrieve sections for an artifact from agent_knowledge_units"""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                knowledge_id,
                agent_id,
                content,
                metadata,
                created_at,
                updated_at
            FROM agent_knowledge_units
            WHERE metadata->>'type' = 'artifact_section'
              AND metadata->>'artifact_id' = %s
            ORDER BY metadata->>'section_id'
        """, (artifact_id,))
        rows = cur.fetchall()
        
        sections = []
        for row in rows:
            meta = row['metadata']
            sections.append({
                'section_id': meta.get('section_id'),
                'title': meta.get('section_title', ''),
                'owner_participant_id': meta.get('owner_participant_id'),
                'status': meta.get('status', 'drafting'),
                'content': row['content'] or '',
                'word_count': meta.get('word_count', 0),
                'citations': meta.get('citations', []),
                'block_type': meta.get('block_type', 'rich_text'),
                'knowledge_id': row['knowledge_id']
            })
        return sections


# ============================================================================
# Routes
# ============================================================================

@router.post("/debates/{debate_id}/artifact/init", response_model=ArtifactInitResponse)
def init_artifact(
    debate_id: str,
    request: ArtifactInitRequest,
    auth: dict = Depends(get_auth_context)
):
    """
    Initialize a new artifact for a debate with section assignments.
    Creates artifact metadata + section placeholders (stored in agent_knowledge_units).
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    try:
        # 1. Verify debate access
        debate = verify_debate_access(debate_id, auth['workspace_id'], conn)
        
        # 2. Get template
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT template_id, title, sections
                FROM artifact_templates
                WHERE template_id = %s
            """, (request.template_id,))
            template = cur.fetchone()
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
            template = dict(template)
        
        # 3. Verify all assigned participants exist in debate
        assignments_map = {a.section_id: a.participant_id for a in request.section_assignments}
        for assignment in request.section_assignments:
            verify_participant_in_debate(assignment.participant_id, debate_id, conn)
        
        # 4. Create artifact
        artifact_id = str(uuid.uuid4())
        title = request.title or template['title']
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO artifacts (
                    artifact_id, debate_id, template_id, title, version, status, created_at
                )
                VALUES (%s, %s, %s, %s, 1, 'drafting', NOW())
            """, (artifact_id, debate_id, request.template_id, title))
        
        # 5. Create section placeholders in agent_knowledge_units
        template_sections = template['sections']
        created_sections = []
        
        for section_def in template_sections:
            section_id = section_def['section_id']
            section_title = section_def['title']
            owner_pid = assignments_map.get(section_id)
            
            # Resolve agent_id from participant
            agent_id = None
            if owner_pid:
                participant = verify_participant_in_debate(owner_pid, debate_id, conn)
                agent_config = participant.get('agent_config', {})
                agent_id = agent_config.get('agent_id')
            
            knowledge_id = str(uuid.uuid4())
            metadata = {
                'type': 'artifact_section',
                'artifact_id': artifact_id,
                'section_id': section_id,
                'section_title': section_title,
                'owner_participant_id': owner_pid,
                'status': 'drafting',
                'block_type': section_def.get('default_block_type', 'rich_text'),
                'citations': [],
                'word_count': 0
            }
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_knowledge_units (
                        knowledge_id, agent_id, source_debate_id, knowledge_type, 
                        content, metadata, created_at
                    )
                    VALUES (%s, %s, %s, 'artifact_section', '', %s, NOW())
                """, (knowledge_id, agent_id, debate_id, psycopg2.extras.Json(metadata)))
            
            created_sections.append(SectionInfo(
                section_id=section_id,
                title=section_title,
                owner_participant_id=owner_pid,
                status='drafting',
                content='',
                word_count=0,
                citations=[],
                block_type=metadata['block_type']
            ))
        
        # 6. Emit artifact_init event
        event_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO events (
                event_id, debate_id, event_type, sender_type, sender_id, sequence_number, content, created_at
            )
            SELECT %s, %s, 'artifact_init', 'system', NULL, 
                   COALESCE(MAX(sequence_number), 0) + 1, %s, NOW()
            FROM events WHERE debate_id = %s
            """, (event_id, debate_id, psycopg2.extras.Json({
            'artifact_id': artifact_id,
            'template_id': request.template_id,
            'title': title,
            'section_count': len(created_sections)
            }), debate_id))
        
        conn.commit()
        
        return ArtifactInitResponse(
            artifact_id=artifact_id,
            debate_id=debate_id,
            template_id=request.template_id,
            title=title,
            version=1,
            status='drafting',
            sections=created_sections,
            created_at=datetime.utcnow().isoformat() + 'Z'
        )
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to init artifact: {str(e)}")
    finally:
        conn.close()


@router.get("/debates/{debate_id}/artifact", response_model=ArtifactGetResponse)
def get_artifact(
    debate_id: str,
    version: Optional[int] = None,
    auth: dict = Depends(get_auth_context)
):
    """
    Get current artifact state (latest version or specific version).
    Reconstructs sections from agent_knowledge_units.
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    try:
        # 1. Verify debate access
        verify_debate_access(debate_id, auth['workspace_id'], conn)
        
        # 2. Get artifact metadata
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if version:
                cur.execute("""
                    SELECT * FROM artifacts
                    WHERE debate_id = %s AND version = %s
                """, (debate_id, version))
            else:
                cur.execute("""
                    SELECT * FROM artifacts
                    WHERE debate_id = %s
                    ORDER BY version DESC
                    LIMIT 1
                """, (debate_id,))
            
            artifact = cur.fetchone()
            if not artifact:
                raise HTTPException(status_code=404, detail="Artifact not found")
            artifact = dict(artifact)
        
        # 3. Get sections
        sections = get_artifact_sections(artifact['artifact_id'], conn)
        
        return ArtifactGetResponse(
            artifact_id=artifact['artifact_id'],
            debate_id=artifact['debate_id'],
            template_id=artifact['template_id'],
            title=artifact['title'],
            version=artifact['version'],
            status=artifact['status'],
            sections=[SectionInfo(**s) for s in sections],
            quality_report=artifact.get('quality_report'),
            created_at=artifact['created_at'].isoformat() + 'Z',
            updated_at=artifact['updated_at'].isoformat() + 'Z',
            finalized_at=artifact['finalized_at'].isoformat() + 'Z' if artifact.get('finalized_at') else None
        )
        
    finally:
        conn.close()


@router.post("/debates/{debate_id}/artifact/sections/{section_id}/events", response_model=SectionEventResponse)
def create_section_event(
    debate_id: str,
    section_id: str,
    request: SectionEventRequest,
    actor_participant_id: str = Header(..., alias="X-Participant-Id"),
    auth: dict = Depends(get_auth_context)
):
    """
    Create a section event (append/replace content, typing indicator).
    Only section owner can write (enforced).
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    try:
        # 1. Verify debate access
        verify_debate_access(debate_id, auth['workspace_id'], conn)
        
        # 2. Verify actor participant
        verify_participant_in_debate(actor_participant_id, debate_id, conn)
        
        # 3. Get artifact + section
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT artifact_id FROM artifacts
                WHERE debate_id = %s
                ORDER BY version DESC
                LIMIT 1
            """, (debate_id,))
            artifact = cur.fetchone()
            if not artifact:
                raise HTTPException(status_code=404, detail="No artifact found for this debate")
            artifact_id = artifact['artifact_id']
        
        # 4. Get section and verify ownership
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT knowledge_id, agent_id, content, metadata
                FROM agent_knowledge_units
                WHERE metadata->>'type' = 'artifact_section'
                  AND metadata->>'artifact_id' = %s
                  AND metadata->>'section_id' = %s
            """, (artifact_id, section_id))
            section = cur.fetchone()
            if not section:
                raise HTTPException(status_code=404, detail="Section not found")
            section = dict(section)
        
        # Enforce ownership
        owner_pid = section['metadata'].get('owner_participant_id')
        if owner_pid and owner_pid != actor_participant_id:
            raise HTTPException(status_code=403, detail="Only section owner can write to this section")
        
        # 5. Update section content based on event type
        if request.event_type == 'replace':
            new_content = request.content
        elif request.event_type == 'append':
            new_content = (section.get('content') or '') + '\n' + request.content
        elif request.event_type == 'typing':
            # Ephemeral event - don't update section content, just log event
            new_content = section.get('content') or ''
        else:
            raise HTTPException(status_code=400, detail="Invalid event_type. Must be: append, replace, typing")
        
        # Update section if not typing
        if request.event_type != 'typing':
            word_count = len(new_content.split())
            updated_metadata = section['metadata'].copy()
            updated_metadata['word_count'] = word_count
            if request.citations:
                updated_metadata['citations'] = (updated_metadata.get('citations', []) + request.citations)
            
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_knowledge_units
                    SET content = %s, metadata = %s, updated_at = NOW()
                    WHERE knowledge_id = %s
                """, (new_content, psycopg2.extras.Json(updated_metadata), section['knowledge_id']))
        
        # 6. Create event in ledger
        event_id = str(uuid.uuid4())
        event_data = {
            'artifact_id': artifact_id,
            'section_id': section_id,
            'event_type': request.event_type,
            'content_preview': request.content[:100] if len(request.content) > 100 else request.content,
            'citations': request.citations or []
        }
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO events (
                    event_id, debate_id, event_type, sender_type, sender_id, sequence_number, content, created_at
                )
                SELECT %s, %s, 'artifact_section_delta', 'participant', %s,
                       COALESCE(MAX(sequence_number), 0) + 1, %s, NOW()
                FROM events WHERE debate_id = %s
            """, (event_id, debate_id, actor_participant_id, psycopg2.extras.Json(event_data), debate_id))
        
        conn.commit()
        
        return SectionEventResponse(
            event_id=event_id,
            section_id=section_id,
            artifact_id=artifact_id,
            event_type=request.event_type,
            actor_participant_id=actor_participant_id,
            content_preview=event_data['content_preview'],
            created_at=datetime.utcnow().isoformat() + 'Z'
        )
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create section event: {str(e)}")
    finally:
        conn.close()


@router.get("/debates/{debate_id}/artifact/events", response_model=ArtifactEventsResponse)
def get_artifact_events(
    debate_id: str,
    section_id: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
    auth: dict = Depends(get_auth_context)
):
    """
    Get artifact event history with cursor pagination.
    Optionally filter by section_id.
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    try:
        # 1. Verify debate access
        verify_debate_access(debate_id, auth['workspace_id'], conn)
        
        # 2. Get artifact_id
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT artifact_id FROM artifacts
                WHERE debate_id = %s
                ORDER BY version DESC
                LIMIT 1
            """, (debate_id,))
            artifact = cur.fetchone()
            if not artifact:
                raise HTTPException(status_code=404, detail="No artifact found")
            artifact_id = artifact['artifact_id']
        
        # 3. Query events with cursor pagination
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if section_id:
                query = """
                    SELECT event_id, debate_id, sender_id, event_type, content, created_at
                    FROM events
                    WHERE debate_id = %s
                      AND event_type LIKE 'artifact_%'
                      AND content->>'artifact_id' = %s
                      AND content->>'section_id' = %s
                """
                params = [debate_id, artifact_id, section_id]
            else:
                query = """
                    SELECT event_id, debate_id, sender_id, event_type, content, created_at
                    FROM events
                    WHERE debate_id = %s
                      AND event_type LIKE 'artifact_%'
                      AND content->>'artifact_id' = %s
                """
                params = [debate_id, artifact_id]
            
            if cursor:
                query += " AND created_at < (SELECT created_at FROM events WHERE event_id = %s)"
                params.append(cursor)
            
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit + 1)  # Fetch one extra to determine if there's a next page
            
            cur.execute(query, params)
            rows = cur.fetchall()
        
        # 4. Build response with next_cursor
        has_more = len(rows) > limit
        events_data = rows[:limit]
        next_cursor = events_data[-1]['event_id'] if has_more and events_data else None
        
        events = []
        for row in events_data:
            events.append(ArtifactEvent(
                event_id=row['event_id'],
                artifact_id=row['content'].get('artifact_id'),
                section_id=row['content'].get('section_id'),
                event_type=row['event_type'],
                actor_participant_id=row.get('sender_id'),
                payload=row['content'],
                created_at=row['created_at'].isoformat() + 'Z'
            ))
        
        return ArtifactEventsResponse(
            events=events,
            next_cursor=next_cursor
        )
        
    finally:
        conn.close()
