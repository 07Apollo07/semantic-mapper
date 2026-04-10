from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

# Define State for the FSDM Discovery Agent
class FSDMDiscoveryState(TypedDict):
    source_info: Dict[str, Any]
    target_info: Dict[str, Any]
    fsdm_instructions: str
    fsdm_lineage_intent: str # Output
    fsdm_status: str # Output
    messages: List[BaseMessage]
    project_name: str
    feedback: Optional[str]

class FSDMIntentOutput(BaseModel):
    lineage_intent: str = Field(description="Explanation of how the source column was derived from FSDM/ETL sources.")
    status: str = Field(description="Status of discovery: e.g., 'Identified', 'Requires_Verification'")

# Define State for the Mapping Agent
class SemanticMappingState(TypedDict):
    source_info: Dict[str, Any]
    target_info: Dict[str, Any]
    transformation_specs: Dict[str, Any]
    global_instructions: str
    mapping_instructions: str
    fsdm_lineage_intent: str # Input from Phase 1
    transformation_logic: str # Output
    reasoning: str # Output
    transformation_type: str # Output
    messages: List[BaseMessage]
    project_name: str
    feedback: Optional[str]

class MappingOutput(BaseModel):
    transformation_type: str = Field(description="Type of transformation: e.g., 1:1, Join, Aggregation, Case expression.")
    transformation_logic: str = Field(description="The complete SQL transformation expression.")
    reasoning: str = Field(description="Detailed logic explanation.")
