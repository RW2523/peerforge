"""
Document Orchestrator
Coordinates agent assignments and document generation during debates
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from .document_service import DocumentService
from ..database import get_db_connection, get_cursor

logger = logging.getLogger(__name__)


class DocumentOrchestrator:
    """Orchestrates document creation and agent assignments during debates"""
    
    def __init__(self):
        self.doc_service = DocumentService()
        
    def initialize_document_for_debate(
        self,
        debate_id: str,
        template_id: str,
        title: str,
        template_sections: List[Dict[str, Any]],
        participants: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Initialize document and auto-assign sections to agents
        
        Args:
            debate_id: Debate UUID
            template_id: Template identifier
            title: Document title
            template_sections: Section definitions from template
            participants: List of debate participants with roles
            
        Returns:
            Created document with assignments
        """
        try:
            # Create document
            document = self.doc_service.create_document(
                debate_id=debate_id,
                template_id=template_id,
                title=title,
                template_sections=template_sections,
                metadata={'auto_assigned': True}
            )
            
            # Auto-assign sections based on strategy
            self._auto_assign_sections(document, participants)
            
            # Mark document as in_progress
            document = self.doc_service.update_document(
                document_id=document['document_id'],
                status='in_progress'
            )
            
            logger.info(f"Initialized document {document['document_id']} for debate {debate_id}")
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to initialize document: {e}", exc_info=True)
            raise
    
    def assign_section_by_role(
        self,
        document_id: str,
        section_key: str,
        role_name: str,
        participants: List[Dict[str, Any]]
    ) -> bool:
        """
        Assign section to agent matching role
        
        Args:
            document_id: Document UUID
            section_key: Section key to assign
            role_name: Role name to match (e.g., "surgeon", "attorney")
            participants: Available participants
            
        Returns:
            True if assigned successfully
        """
        # Find participant with matching role
        agent = self._find_agent_by_role(participants, role_name)
        
        if not agent:
            logger.warning(f"No agent found with role '{role_name}' for section '{section_key}'")
            return False
        
        # Get section ID
        document = self.doc_service.get_document(document_id)
        section = next((s for s in document['sections'] if s['section_key'] == section_key), None)
        
        if not section:
            logger.error(f"Section '{section_key}' not found in document {document_id}")
            return False
        
        # Assign
        try:
            self.doc_service.assign_section(
                section_id=section['section_id'],
                agent_id=agent.get('agent_id'),
                agent_name=agent.get('name')
            )
            logger.info(f"Assigned section '{section_key}' to agent '{agent.get('name')}'")
            return True
        except Exception as e:
            logger.error(f"Failed to assign section: {e}")
            return False
    
    def mark_section_in_progress(
        self,
        section_id: str,
        agent_name: str
    ):
        """Mark section as being written by agent"""
        try:
            self.doc_service.update_section_progress(
                section_id=section_id,
                status='in_progress'
            )
            logger.info(f"Section {section_id} marked in progress by {agent_name}")
        except Exception as e:
            logger.error(f"Failed to mark section in progress: {e}")
    
    def complete_section(
        self,
        section_id: str,
        word_count: int,
        agent_name: str
    ):
        """Mark section as completed"""
        try:
            self.doc_service.update_section_progress(
                section_id=section_id,
                word_count=word_count,
                status='completed'
            )
            logger.info(f"Section {section_id} completed by {agent_name} ({word_count} words)")
        except Exception as e:
            logger.error(f"Failed to complete section: {e}")
    
    def get_agent_sections(
        self,
        document_id: str,
        agent_name: str
    ) -> List[Dict[str, Any]]:
        """Get all sections assigned to an agent"""
        document = self.doc_service.get_document(document_id)
        
        return [
            s for s in document['sections']
            if s.get('assigned_agent_name') == agent_name
        ]
    
    def get_pending_sections(
        self,
        document_id: str
    ) -> List[Dict[str, Any]]:
        """Get sections that need to be written"""
        document = self.doc_service.get_document(document_id)
        
        return [
            s for s in document['sections']
            if s['status'] in ['pending', 'assigned']
        ]
    
    def is_document_complete(self, document_id: str) -> bool:
        """Check if all sections are completed"""
        document = self.doc_service.get_document(document_id)
        
        return all(
            s['status'] == 'completed'
            for s in document['sections']
        )
    
    # ========================================================================
    # Private Helpers
    # ========================================================================
    
    def _auto_assign_sections(
        self,
        document: Dict[str, Any],
        participants: List[Dict[str, Any]]
    ):
        """Auto-assign sections based on assignment strategy"""
        
        for section in document['sections']:
            strategy = section.get('assignment_strategy')
            
            if strategy == 'host':
                # Assign to ultimate host
                host = self._find_ultimate_host(participants)
                if host:
                    self.doc_service.assign_section(
                        section_id=section['section_id'],
                        agent_name='Review Chair'
                    )
                    
            elif strategy == 'role':
                # Assign based on role in template
                # Section title might contain role hint
                # This is simplified - frontend should handle better
                pass
                
            elif strategy == 'auto':
                # Round-robin assignment
                if participants:
                    idx = len([s for s in document['sections'] 
                              if s.get('assigned_agent_name')]) % len(participants)
                    agent = participants[idx]
                    self.doc_service.assign_section(
                        section_id=section['section_id'],
                        agent_id=agent.get('agent_id'),
                        agent_name=agent.get('name')
                    )
    
    def _find_agent_by_role(
        self,
        participants: List[Dict[str, Any]],
        role_name: str
    ) -> Optional[Dict[str, Any]]:
        """Find agent matching role name"""
        role_lower = role_name.lower().replace('_', ' ').replace('-', ' ')
        
        for participant in participants:
            agent_role = participant.get('role_description', '').lower()
            agent_name = participant.get('name', '').lower()
            
            if role_lower in agent_role or role_lower in agent_name:
                return participant
        
        return None
    
    def _find_ultimate_host(
        self,
        participants: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find Review Chair (or legacy Ultimate Host) in participants."""
        for participant in participants:
            name_lower = participant.get('name', '').lower()
            if 'review chair' in name_lower or 'ultimate host' in name_lower:
                return participant
        return None
