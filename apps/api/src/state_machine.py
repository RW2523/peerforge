"""Debate state machine and transition logic"""
from enum import Enum
from typing import Optional


class DebateState(str, Enum):
    """Debate lifecycle states"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    ENDED = "ended"


class StateTransitionError(Exception):
    """Invalid state transition attempted"""
    pass


class DebateStateMachine:
    """
    Debate state machine with transition validation
    
    Valid transitions:
    - pending -> running (start)
    - running -> paused (pause)
    - running -> ended (end)
    - paused -> running (resume)
    - paused -> ended (end)
    """
    
    VALID_TRANSITIONS = {
        DebateState.PENDING: [DebateState.RUNNING],
        DebateState.RUNNING: [DebateState.PAUSED, DebateState.ENDED],
        DebateState.PAUSED: [DebateState.RUNNING, DebateState.ENDED],
        DebateState.ENDED: []  # Terminal state
    }
    
    @classmethod
    def can_transition(cls, from_state: DebateState, to_state: DebateState) -> bool:
        """Check if transition is valid"""
        return to_state in cls.VALID_TRANSITIONS.get(from_state, [])
    
    @classmethod
    def validate_transition(cls, from_state: DebateState, to_state: DebateState) -> None:
        """Validate transition or raise error"""
        if not cls.can_transition(from_state, to_state):
            raise StateTransitionError(
                f"Invalid transition from {from_state.value} to {to_state.value}"
            )
    
    @classmethod
    def can_start(cls, state: DebateState) -> bool:
        """Check if debate can be started"""
        return state == DebateState.PENDING
    
    @classmethod
    def can_pause(cls, state: DebateState) -> bool:
        """Check if debate can be paused"""
        return state == DebateState.RUNNING
    
    @classmethod
    def can_resume(cls, state: DebateState) -> bool:
        """Check if debate can be resumed"""
        return state == DebateState.PAUSED
    
    @classmethod
    def can_intervene(cls, state: DebateState) -> bool:
        """Check if intervention is allowed"""
        return state in [DebateState.RUNNING, DebateState.PAUSED]
    
    @classmethod
    def can_end(cls, state: DebateState) -> bool:
        """Check if debate can be ended"""
        return state in [DebateState.RUNNING, DebateState.PAUSED]
    
    @classmethod
    def is_active(cls, state: DebateState) -> bool:
        """Check if debate is in active state (not ended)"""
        return state != DebateState.ENDED
