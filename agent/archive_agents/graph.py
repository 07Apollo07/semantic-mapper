# from typing import TypedDict, List, Dict, Any, Literal, Union
# from pydantic import BaseModel, Field
# from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolNode
# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_community.utilities import SQLDatabase
# from logic.project_manager import ProjectManager
# from dotenv import load_dotenv

# load_dotenv()

# # Define the structured output models
# class TransformationOutput(BaseModel):
#     transformation_type: str = Field(description="Type of transformation: e.g., 1:1 mapping, rename, Left-Join, Right join, Outer Join, Inner Join, aggregation etc.")
#     transformation_logic: str = Field(description="The complete single-line SQL transforming source column(s) to the target semantic column.")
#     reasoning: str = Field(description="Short explanation why this transformation is needed, citing evidence from context and tools.")

# class IntentOutput(BaseModel):
#     mapping_intent: str = Field(description="The core technical hypothesis of how the source maps to the target.")
#     reasoning: str = Field(description="Detailed reasoning for this mapping, citing evidence from context and tools.")
#     pseudocode: str = Field(description="SQL-like pseudocode of the transformation logic.")

# # Define the state for the graph
# class AgentState(TypedDict):
#     source_info: Dict[str, Any]
#     target_info: Dict[str, Any]
#     transformation_specs: Dict[str, Any]
#     context: str
#     project_name: str
#     messages: List[BaseMessage]
#     transformation_type: str
#     transformation_logic: str
#     reasoning: str
#     feedback: str
#     global_instructions: str
#     pre_mapping_insight: str
#     tool_call_count: int

# def create_agent(retriever, model_name="gpt-4o", api_key=None, base_url=None, log_callback=None, project_name=None):
#     """Simplified agent that gathers all context upfront and performs a one-shot mapping."""
#     if not model_name:
#         raise ValueError("model_name must be a non-empty string")

#     def _log(msg):
#         if log_callback:
#             log_callback(msg)
#         print(msg)

#     # Initialize the LLM
#     llm = ChatOpenAI(
#         model=model_name,
#         temperature=0.1,
#         api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
#         base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
#     )

#     # We only bind the output tool
#     llm_with_tools = llm.bind_tools([TransformationOutput])

#     # Import tools for upfront context gathering
#     # from ..tools.tools import get_table_schema, search_documentation

#     def init_node(state: AgentState):
#         """Gathers all technical and documentation context before invoking the LLM."""
#         s = state['source_info']
#         t = state['target_info']
#         project_name = state['project_name']
#         s_tbl = s.get('table_name')
#         t_tbl = t.get('table_name')
        
#         # 1. Build initial query for vector store context (Rich Retrieval)
#         query_parts = []
#         def add_parts(prefix, val):
#             if not val or val == "N/A": return
#             sub_parts = [p.strip() for p in str(val).split(',') if p.strip()]
#             for p in sub_parts:
#                 query_parts.append(f"{prefix}: {p}")

#         add_parts("Source DB", s.get('db_name'))
#         add_parts("Source Table", s.get('table_name'))
#         add_parts("Source Column", s.get('column_name'))
#         add_parts("Target DB", t.get('db_name'))
#         add_parts("Target Table", t.get('table_name'))
#         add_parts("Target Column", t.get('column_name'))
        
#         query = " | ".join(query_parts)
#         if not query:
#             query = "No specific source/target info provided."

#         _log(f"🔍 [Agent: Init] Vector Retrieval Query: {query}")
#         docs = retriever.invoke(query)
#         doc_context = "\n\n".join([doc.page_content for doc in docs])
#         _log(f"✅ [Agent: Init] Vector context retrieved ({len(doc_context)} bytes).")

#         # 2. Fetch FSDM/ETL Documentation (Structured context)
#         _log(f"🔎 [Agent: Init] Querying fsdm_etl_ sheets for source table: {s_tbl}...")
#         fsdm_context = search_documentation.invoke({"query_term": s_tbl, "project_name": project_name}) if s_tbl else "No source table provided."
#         _log(f"✅ [Agent: Init] FSDM context retrieved ({len(fsdm_context)} bytes).")

#         # 3. Fetch Technical Schemas
#         _log(f"📋 [Agent: Init] Fetching technical schemas for {s_tbl} and {t_tbl}...")
#         s_schema = get_table_schema.invoke({"table_name": s_tbl, "project_name": project_name}) if s_tbl else ""
#         t_schema = get_table_schema.invoke({"table_name": t_tbl, "project_name": project_name}) if t_tbl else ""

#         system_prompt_content = f"""You are a Senior Data Engineer and SQL Architect.
# Your goal is to provide a single-line SQL transformation that maps a source column to a target semantic column.

# <technical_schemas>
# SOURCE TABLE ({s_tbl}):
# {s_schema}

# TARGET TABLE ({t_tbl}):
# {t_schema}
# </technical_schemas>

# <verified_intent_and_logic>
# {state.get('pre_mapping_insight', 'None')}
# </verified_intent_and_logic>

# <fsdm_etl_documentation>
# {fsdm_context}
# </fsdm_etl_documentation>

# <unstructured_documentation_snippets>
# {doc_context if doc_context else "No documentation found."}
# </unstructured_documentation_snippets>

# <global_instructions>
# {state.get('global_instructions', 'None')}
# </global_instructions>

# <strict_rules>
# 1. The transformation logic MUST be a single-line SQL expression.
# 2. Do NOT use WHERE clauses in the mapping logic.
# 3. Be precise with table and column names. Use double-quotes if names contain spaces or special characters.
# 4. If a JOIN is implied by the verified intent, represent the transformation of the source field accordingly.
# 5. YOU MUST FINISH BY CALLING THE `TransformationOutput` tool.
# </strict_rules>

# <mapping_guidelines>
# 1. Decide the appropriate transformation type (rename, 1:1 mapping, join, aggregation, etc.).
# 2. If multiple source databases or tables are mentioned, they likely require a JOIN.
# 3. For multiple source columns, determine the relationship (e.g., concatenation, arithmetic, or join keys).
# 4. Use provided context and Transformation Specs as strong requirements for the logic.
# </mapping_guidelines>
# """
#         user_content = f"""
# Transform source column into semantic column.

# SOURCE DATA:
# - Subject Area: {s.get('subject_area', 'N/A')}
# - Database: {s.get('db_name', 'N/A')}
# - Table: {s.get('table_name', 'N/A')}
# - Column: {s.get('column_name', 'N/A')}
# - Datatype: {s.get('datatype', 'N/A')}

# TARGET (SEMANTIC) DATA:
# - Subject Area: {t.get('subject_area', 'N/A')}
# - Database: {t.get('db_name', 'N/A')}
# - Table: {t.get('table_name', 'N/A')}
# - Column: {t.get('column_name', 'N/A')}
# - Datatype: {t.get('datatype', 'N/A')}

# TRANSFORMATION SPECS (FROM MAPPING DOCUMENT):
# - Provided Type: {state['transformation_specs'].get('type', 'N/A')}
# - Provided Condition: {state['transformation_specs'].get('condition', 'N/A')}
# - Remarks: {state['transformation_specs'].get('remarks', 'N/A')}

# FEEDBACK/CORRECTION:
# {state.get('feedback', 'None')}

# Provide the final SQL transformation via TransformationOutput tool.
# """
#         _log(f"👤 [Agent: Init] Context gathered and prompt prepared.")
#         return {
#             "messages": [SystemMessage(content=system_prompt_content), HumanMessage(content=user_content)]
#         }

#     def agent_node(state: AgentState):
#         """Single-shot LLM invocation with full tracing."""
#         _log("--- Agent Prompt Construction ---")
#         for msg in state['messages']:
#             _log(f"[{msg.type.upper()} MESSAGE]:\n{msg.content}\n---")
            
#         _log(f"🚀 [Agent: Invoke] Generating transformation...")
#         response = llm_with_tools.invoke(state['messages'])
        
#         _log(f"◀️ [Agent: Result] LLM Response Content: {response.content}")
#         if response.tool_calls:
#              _log(f"◀️ [Agent: Result] LLM Tool Calls: {response.tool_calls}")
             
#         return {"messages": [response]}

#     def process_node(state: AgentState):
#         """Extracts the final structured output."""
#         last_message = state['messages'][-1]
#         output_call = next((tc for tc in last_message.tool_calls if tc['name'] == 'TransformationOutput'), None)
#         if output_call:
#             args = output_call['args']
#             _log(f"✅ [Agent: Done] Transformation Logic: {args.get('transformation_logic')}")
#             return {
#                 "transformation_type": args.get('transformation_type'),
#                 "transformation_logic": args.get('transformation_logic'),
#                 "reasoning": args.get('reasoning')
#             }
        
#         _log("⚠️ [Agent: Process] Failed to get structured output. Using fallback.")
#         return {
#             "transformation_type": "1:1 Mapping",
#             "transformation_logic": "-- Failed to generate structured logic",
#             "reasoning": "Model did not provide a valid tool call."
#         }

#     workflow = StateGraph(AgentState)
#     workflow.add_node("init", init_node)
#     workflow.add_node("agent", agent_node)
#     workflow.add_node("process", process_node)

#     workflow.set_entry_point("init")
#     workflow.add_edge("init", "agent")
#     workflow.add_edge("agent", "process")
#     workflow.add_edge("process", END)

#     return workflow.compile()

# def create_intent_agent(retriever, model_name="gpt-4o", api_key=None, base_url=None, log_callback=None, project_name="default"):
#     """
#     Simplified Intent Agent that gathers context upfront and performs a single LLM invocation.
#     No more LangGraph or tool-calling loops for the agent itself.
#     """
#     if not model_name or not isinstance(model_name, str):
#         raise ValueError("model_name must be a non-empty string")

#     def _log(msg):
#         if log_callback:
#             log_callback(msg)
#         print(msg)

#     # Use the same tools we defined, but call them synchronously here
#     from agent.tools.tools import get_business_schema_summary, get_table_schema, fetch_vector_context, search_documentation
    
#     def invoke(state: AgentState):
#         _log(f"🔍 [Intent-Agent] Starting simplified intent flow...")
        
#         s = state.get('source_info', {})
#         t = state.get('target_info', {})
#         s_tbl = s.get('table_name')
        
#         # 1. Fetch Vector Store Context (Core Context)
#         _log("🔍 [Intent-Agent] Fetching core context from vector store...")
#         query_parts = []
#         def add_parts(prefix, val):
#             if not val or val == "N/A": return
#             sub_parts = [p.strip() for p in str(val).split(',') if p.strip()]
#             for p in sub_parts:
#                 query_parts.append(f"{prefix}: {p}")

#         add_parts("Source DB", s.get('db_name'))
#         add_parts("Source Table", s.get('table_name'))
#         add_parts("Source Column", s.get('column_name'))
#         add_parts("Target DB", t.get('db_name'))
#         add_parts("Target Table", t.get('table_name'))
#         add_parts("Target Column", t.get('column_name'))
        
#         query = " | ".join(query_parts)
#         if not query:
#             query = "No specific source/target info provided."

#         _log(f"🔍 [Intent-Agent] Richer Retrieval Query: {query}")
#         doc_context = fetch_vector_context.invoke({"query": query, "project_name": project_name})
#         _log(f"✅ [Intent-Agent] Vector context retrieved.")

#         # 2. Fetch FSDM/ETL Context (Filtered by Source Table)
#         _log(f"🔎 [Intent-Agent] Querying fsdm_etl_ sheets for source table: {s_tbl}...")
#         fsdm_context = search_documentation.invoke({"query_term": s_tbl, "project_name": project_name}) if s_tbl else "No source table provided."
#         _log(f"✅ [Intent-Agent] FSDM context retrieved.")

#         # 3. Simplify Prompts
#         system_prompt = f"""You are a Data Architect. Your goal is to provide a technical intent for a column mapping.
# Analyze the provided context and formulate a hypothesis.

# <core_context_from_docs>
# {doc_context if doc_context else "No documentation found."}
# </core_context_from_docs>

# <source_table_fsdm_metadata>
# {fsdm_context}
# </source_table_fsdm_metadata>

# <operational_rules>
# 1. Analyze the mapping between source and target.
# 2. Provide a clear reasoning.
# 3. Provide SQL-like pseudocode.
# 4. YOU MUST FINISH BY CALLING THE `IntentOutput` tool.
# </operational_rules>
# """

#         user_content = f"""
# Transform source column into semantic column.

# SOURCE DATA:
# - Subject Area: {s.get('subject_area', 'N/A')}
# - Database: {s.get('db_name', 'N/A')}
# - Table: {s.get('table_name', 'N/A')}
# - Column: {s.get('column_name', 'N/A')}
# - Datatype: {s.get('datatype', 'N/A')}

# TARGET (SEMANTIC) DATA:
# - Subject Area: {t.get('subject_area', 'N/A')}
# - Database: {t.get('db_name', 'N/A')}
# - Table: {t.get('table_name', 'N/A')}
# - Column: {t.get('column_name', 'N/A')}
# - Datatype: {t.get('datatype', 'N/A')}

# TRANSFORMATION SPECS (FROM MAPPING DOCUMENT):
# - Provided Type: {state['transformation_specs'].get('type', 'N/A')}
# - Provided Condition: {state['transformation_specs'].get('condition', 'N/A')}
# - Remarks: {state['transformation_specs'].get('remarks', 'N/A')}

# FEEDBACK/CORRECTION:
# {state.get('feedback', 'None')}

# Based on the context, what is the best technical intent for this mapping? Give me the intent, reasoning and pseudocode.
# """

#         # Invoke LLM
#         llm = ChatOpenAI(
#             model=model_name,
#             temperature=0.1,
#             api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
#             base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
#         )
#         llm_with_tools = llm.bind_tools([IntentOutput])
        
#         _log(f"🚀 [Intent-Agent] Invoking LLM...")
#         response = llm_with_tools.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_content)])
#         _log(f"◀️ [Intent-Agent] Response received.")
        
#         # Extract output
#         mapping_intent = ""
#         reasoning = ""
#         pseudocode = ""
        
#         if hasattr(response, 'tool_calls') and response.tool_calls:
#             for tc in response.tool_calls:
#                 if tc['name'] == 'IntentOutput':
#                     args = tc['args']
#                     mapping_intent = args.get('mapping_intent', '')
#                     reasoning = args.get('reasoning', '')
#                     pseudocode = args.get('pseudocode', '')
#                     break
        
#         if not mapping_intent:
#             _log("⚠️ [Intent-Agent] Model failed tool call. Using content.")
#             mapping_intent = response.content[:200] + "..."
#             reasoning = "Extracted from raw response."
#             pseudocode = "-- Not provided"

#         formatted_insight = f"""**Intent:** {mapping_intent}

# **Reasoning:** {reasoning}

# **Pseudocode:**
# ```sql
# {pseudocode}
# ```"""
#         return {"pre_mapping_insight": formatted_insight}

#     # Return a class that mimics the Runnable interface
#     class SimplifiedAgent:
#         def invoke(self, state: AgentState):
#             return invoke(state)
            
#     return SimplifiedAgent()
