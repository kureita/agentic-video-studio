"""Agent Orchestrator - The brain of the Workflow AI Agent."""

import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from app.services.llm import get_llm
from app.prompts.workflow_agent import get_workflow_agent_prompt


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" | "assistant" | "system"
    content: str


class AgentAction(BaseModel):
    """A single action to perform on the workflow."""
    type: str  # "addNode" | "removeNode" | "updateNode" | "addEdge" | "removeEdge"
    node: Optional[Dict[str, Any]] = None
    nodeId: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    edge: Optional[Dict[str, Any]] = None
    edgeId: Optional[str] = None


class AgentResponse(BaseModel):
    """Response from the agent orchestrator."""
    intent: str  # "create" | "edit" | "brainstorm" | "explain"
    thinking: str
    message: str
    actions: List[AgentAction] = []


class WorkflowState(BaseModel):
    """Current state of the workflow."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []


class AgentOrchestrator:
    """Orchestrates AI agent interactions for workflow building."""

    def __init__(self, provider: str = "openai"):
        """
        Initialize the orchestrator.
        
        Args:
            provider: LLM provider ("openai", "claude", or "gemini")
        """
        self.provider = provider
        self.llm = get_llm(provider)
        self.system_prompt = get_workflow_agent_prompt()

    def _build_user_prompt(
        self,
        messages: List[ChatMessage],
        workflow: Optional[WorkflowState] = None,
    ) -> str:
        """Build the prompt to send to the LLM."""
        # Include conversation history
        conversation = "\n".join([
            f"{msg.role.upper()}: {msg.content}"
            for msg in messages[-10:]  # Keep last 10 messages for context
        ])
        
        # Include current workflow state if present
        workflow_context = ""
        if workflow and (workflow.nodes or workflow.edges):
            workflow_context = f"""

## Current Workflow State:
Nodes: {json.dumps(workflow.nodes, indent=2)}
Edges: {json.dumps(workflow.edges, indent=2)}
"""
        
        return f"""## Conversation:
{conversation}
{workflow_context}

Respond with valid JSON following the schema in the system prompt."""

    async def process(
        self,
        messages: List[ChatMessage],
        workflow: Optional[WorkflowState] = None,
    ) -> AgentResponse:
        """
        Process a conversation and return the agent response.
        
        Args:
            messages: Conversation history
            workflow: Current workflow state (nodes/edges)
            
        Returns:
            AgentResponse with intent, thinking, message, and actions
        """
        user_prompt = self._build_user_prompt(messages, workflow)
        
        try:
            response_text = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=self.system_prompt,
                temperature=0.7,
                json_response=True,
            )
            
            # Parse the JSON response
            response_data = json.loads(response_text)
            
            # Convert actions to proper format
            actions = []
            for action_data in response_data.get("actions", []):
                actions.append(AgentAction(**action_data))
            
            return AgentResponse(
                intent=response_data.get("intent", "brainstorm"),
                thinking=response_data.get("thinking", ""),
                message=response_data.get("message", "I processed your request."),
                actions=actions,
            )
            
        except json.JSONDecodeError as e:
            return AgentResponse(
                intent="error",
                thinking=f"Failed to parse LLM response: {str(e)}",
                message="I encountered an error processing your request. Please try again.",
                actions=[],
            )
        except Exception as e:
            return AgentResponse(
                intent="error",
                thinking=f"Error: {str(e)}",
                message=f"An error occurred: {str(e)}",
                actions=[],
            )

    async def process_stream(
        self,
        messages: List[ChatMessage],
        workflow: Optional[WorkflowState] = None,
    ):
        """
        Process a conversation with streaming response.
        
        Yields:
            Dict with type ("thinking", "message", "action", "complete") and data
        """
        user_prompt = self._build_user_prompt(messages, workflow)
        
        # First, yield a thinking status
        yield {"type": "status", "data": "Analyzing your request..."}
        
        try:
            # Collect the full response for JSON parsing
            full_response = ""
            async for chunk in self.llm.stream(
                prompt=user_prompt,
                system_prompt=self.system_prompt,
                temperature=0.7,
            ):
                full_response += chunk
                yield {"type": "chunk", "data": chunk}
            
            # Parse the complete response
            try:
                response_data = json.loads(full_response)
                
                # Yield thinking
                if response_data.get("thinking"):
                    yield {"type": "thinking", "data": response_data["thinking"]}
                
                # Yield each action individually
                for action in response_data.get("actions", []):
                    yield {"type": "action", "data": action}
                
                # Yield final message
                yield {"type": "message", "data": response_data.get("message", "Done!")}
                
                # Complete
                yield {"type": "complete", "data": response_data}
                
            except json.JSONDecodeError:
                yield {"type": "error", "data": "Failed to parse response as JSON"}
                
        except Exception as e:
            yield {"type": "error", "data": str(e)}


def get_orchestrator(provider: str = "openai") -> AgentOrchestrator:
    """Get an agent orchestrator instance."""
    return AgentOrchestrator(provider=provider)
