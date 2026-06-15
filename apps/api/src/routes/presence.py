"""
Presence & Typing API Routes (TICKET-14)
Endpoints for realtime presence and typing indicators
"""

import psycopg2
from psycopg2.extras import Json
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from src.config import settings
from src.auth import require_auth

router = APIRouter()


# Request/Response Models

class PresenceJoinRequest(BaseModel):
    participant_id: Optional[str] = None  # If human/observer
    metadata: dict = {}


class PresenceLeaveRequest(BaseModel):
    participant_id: Optional[str] = None


class TypingRequest(BaseModel):
    participant_id: Optional[str] = None
    target_participant_id: Optional[str] = None  # Who they're responding to


class PresenceResponse(BaseModel):
    event_id: str
    debate_id: str
    event_type: str
    sequence_number: int
    created_at: datetime


# Helper functions

def check_workspace_access(workspace_id: str, auth_workspace_id: str):
    """Check if user has access to workspace"""
    if workspace_id != auth_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to workspace"
        )


def get_debate_workspace(debate_id: str) -> str:
    """Get workspace_id for a debate"""
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT workspace_id FROM debates WHERE debate_id = %s", (debate_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Debate {debate_id} not found"
            )
        return result[0]
    finally:
        cursor.close()
        conn.close()


# Endpoints

@router.post("/debates/{debate_id}/presence/join", response_model=PresenceResponse)
def join_presence(
    debate_id: str,
    request: PresenceJoinRequest,
    workspace_id: str = Depends(require_auth)
):
    """
    Signal presence join (user/agent coming online)
    
    Creates a presence_update event in the events ledger.
    SSE clients will receive this to update presence indicators.
    
    Protected: Requires valid JWT and workspace access
    """
    debate_workspace = get_debate_workspace(debate_id)
    check_workspace_access(debate_workspace, workspace_id)
    
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Get next sequence number (scoped to this debate)
        cursor.execute("""
            SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
            FROM events
            WHERE debate_id = %s
        """, (debate_id,))
        next_seq = cursor.fetchone()[0]
        
        # Insert presence event
        cursor.execute("""
            INSERT INTO events (
                event_id, debate_id, event_type, sender_type, sender_id,
                sequence_number, content, created_at
            ) VALUES (
                gen_random_uuid(), %s, 'presence_update', 'system', NULL,
                %s, %s, NOW()
            )
            RETURNING event_id, debate_id, event_type, sequence_number, created_at
        """, (
            debate_id,
            next_seq,
            Json({
                'action': 'join',
                'participant_id': request.participant_id,
                'metadata': request.metadata
            })
        ))
        
        result = cursor.fetchone()
        conn.commit()
        
        return PresenceResponse(
            event_id=result[0],
            debate_id=result[1],
            event_type=result[2],
            sequence_number=result[3],
            created_at=result[4]
        )
    
    finally:
        cursor.close()
        conn.close()


@router.post("/debates/{debate_id}/presence/leave", response_model=PresenceResponse)
def leave_presence(
    debate_id: str,
    request: PresenceLeaveRequest,
    workspace_id: str = Depends(require_auth)
):
    """
    Signal presence leave (user/agent going offline)
    
    Creates a presence_update event in the events ledger.
    
    Protected: Requires valid JWT and workspace access
    """
    debate_workspace = get_debate_workspace(debate_id)
    check_workspace_access(debate_workspace, workspace_id)
    
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Get next sequence number (scoped to this debate)
        cursor.execute("""
            SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
            FROM events
            WHERE debate_id = %s
        """, (debate_id,))
        next_seq = cursor.fetchone()[0]
        
        # Insert presence event
        cursor.execute("""
            INSERT INTO events (
                event_id, debate_id, event_type, sender_type, sender_id,
                sequence_number, content, created_at
            ) VALUES (
                gen_random_uuid(), %s, 'presence_update', 'system', NULL,
                %s, %s, NOW()
            )
            RETURNING event_id, debate_id, event_type, sequence_number, created_at
        """, (
            debate_id,
            next_seq,
            Json({
                'action': 'leave',
                'participant_id': request.participant_id
            })
        ))
        
        result = cursor.fetchone()
        conn.commit()
        
        return PresenceResponse(
            event_id=result[0],
            debate_id=result[1],
            event_type=result[2],
            sequence_number=result[3],
            created_at=result[4]
        )
    
    finally:
        cursor.close()
        conn.close()


@router.post("/debates/{debate_id}/typing", response_model=PresenceResponse)
def signal_typing(
    debate_id: str,
    request: TypingRequest,
    workspace_id: str = Depends(require_auth)
):
    """
    Signal typing indicator (agent is generating response)
    
    Creates a typing event in the events ledger.
    Ephemeral in nature but stored for audit/replay.
    
    Protected: Requires valid JWT and workspace access
    """
    debate_workspace = get_debate_workspace(debate_id)
    check_workspace_access(debate_workspace, workspace_id)
    
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        # Get next sequence number (scoped to this debate)
        cursor.execute("""
            SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
            FROM events
            WHERE debate_id = %s
        """, (debate_id,))
        next_seq = cursor.fetchone()[0]
        
        # Insert typing event
        cursor.execute("""
            INSERT INTO events (
                event_id, debate_id, event_type, sender_type, sender_id,
                sequence_number, content, created_at
            ) VALUES (
                gen_random_uuid(), %s, 'typing', 'system', NULL,
                %s, %s, NOW()
            )
            RETURNING event_id, debate_id, event_type, sequence_number, created_at
        """, (
            debate_id,
            next_seq,
            Json({
                'participant_id': request.participant_id,
                'target_participant_id': request.target_participant_id
            })
        ))
        
        result = cursor.fetchone()
        conn.commit()
        
        return PresenceResponse(
            event_id=result[0],
            debate_id=result[1],
            event_type=result[2],
            sequence_number=result[3],
            created_at=result[4]
        )
    
    finally:
        cursor.close()
        conn.close()
