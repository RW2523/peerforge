"""Agent-related endpoints"""
from fastapi import APIRouter, Depends, status
from typing import List, Dict, Any
from ..auth import get_current_user, check_workspace_access
from ..agent_templates import get_all_templates
from ..agent_service import AgentService
from ..schemas.agents import (
    AgentTemplateResponse,
    CreateAgentRequest,
    AgentResponse,
)

router = APIRouter()


@router.get("/agent-templates", response_model=List[AgentTemplateResponse])
async def list_agent_templates(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List built-in agent templates (roles + personas).

    Protected: Requires valid JWT (disabled in tests/local dev).
    """
    _ = current_user  # auth gate
    return [AgentTemplateResponse(**t) for t in get_all_templates()]


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: CreateAgentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a persistent agent definition for reuse across meetings.

    Protected: Requires valid JWT and workspace access.
    """
    check_workspace_access(current_user, request.workspace_id)

    svc = AgentService()
    agent = svc.create_agent(
        workspace_id=request.workspace_id,
        name=request.name,
        role_description=request.role_description,
        system_prompt=request.system_prompt,
        model_id=request.model_id,
        model_config=request.agent_model_config or {},
    )

    return AgentResponse(
        agent_id=agent["agent_id"],
        workspace_id=str(agent["workspace_id"]),
        name=agent["name"],
        role_description=agent.get("role_description"),
        system_prompt=agent.get("system_prompt") or "",
        model_id=agent.get("model_id") or "",
        llm_config=agent.get("model_config") or {},
        created_at=agent["created_at"].isoformat(),
    )


@router.get("/agents", response_model=List[AgentResponse])
async def list_agents(
    workspace_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List persistent agents in a workspace.

    Protected: Requires valid JWT and workspace access.
    """
    check_workspace_access(current_user, workspace_id)

    svc = AgentService()
    agents = svc.list_agents(workspace_id)
    return [
        AgentResponse(
            agent_id=a["agent_id"],
            workspace_id=str(a["workspace_id"]),
            name=a["name"],
            role_description=a.get("role_description"),
            system_prompt=a.get("system_prompt") or "",
            model_id=a.get("model_id") or "",
            llm_config=a.get("model_config") or {},
            created_at=a["created_at"].isoformat(),
        )
        for a in agents
    ]
