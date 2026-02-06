from typing import List, Dict, Any, Optional
import uuid
from pydantic import BaseModel, Field

class Node(BaseModel):
    id: str = Field(..., description="Unique identifier for the node")
    type: str = Field(..., description="Type of the node (e.g., 'url_input', 'summarizer', 'video_gen')")
    data: Dict[str, Any] = Field(default_factory=dict, description="Configuration data for the node")
    position: Optional[Dict[str, float]] = Field(None, description="Optional UI position {x, y}")

class Edge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the edge")
    source: str = Field(..., description="ID of the source node")
    target: str = Field(..., description="ID of the target node")
    label: Optional[str] = Field(None, description="Optional label for the connection")

class GraphPlan(BaseModel):
    nodes: List[Node] = Field(..., description="List of nodes in the workflow")
    edges: List[Edge] = Field(..., description="List of connections between nodes")
    narrative: str = Field(..., description="Explanation of why this graph was built")
