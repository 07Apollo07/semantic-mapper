from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

# Define State for the FSDM Discovery Agent
class FSDMDiscoveryState(TypedDict):
    source_info: Dict[str, Any]
    target_info: Dict[str, Any]
    fsdm_instructions: str
    metadata: str  # Metadata for the specific FSDM table being analyzed
    fsdm_lineage_intent: str # Output
    fsdm_status: str # Output
    messages: Annotated[List[BaseMessage], add_messages]
    project_name: str
    feedback: Optional[str]
    system_prompt: Optional[str] # Cache for the system prompt

class FSDMIntentOutput(BaseModel):
    lineage_intent: str = Field(description="Detailed explanation of the lineage chain (e.g., A -> B -> C).")
    findings: str = Field(description="Brief summary of what was found.")
    reasoning: str = Field(description="Step-by-step logic used to trace the lineage.")
    recommended_sources: List[str] = Field(description="List of tables or columns identified as the right sources.")

# Define State for the Mapping Agent
class SemanticMappingState(TypedDict):
    source_info: Dict[str, Any]
    target_info: Dict[str, Any]
    transformation_specs: Dict[str, Any]
    global_instructions: str
    mapping_instructions: str
    fsdm_lineage_intent: Dict[str, Any] # Full Discovery Report from Phase 1
    vector_context: str # Context from Vector Store
    transformation_logic: str # Output
    reasoning: str # Output
    transformation_type: str # Output
    messages: Annotated[List[BaseMessage], add_messages]
    project_name: str
    feedback: Optional[str]
    system_prompt: Optional[str] # Cache for the system prompt

class MappingOutput(BaseModel):
    transformation_type: str = Field(description="Type of transformation: e.g., 1:1, Join, Aggregation, Case expression.")
    transformation_logic: str = Field(description="The complete SQL transformation expression.")
    reasoning: str = Field(description="Detailed logic explanation.")
