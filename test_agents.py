import os
import pandas as pd
from typing import Dict, Any
from agent.executor import AgentExecutor
from logic.state import AppState
from unittest.mock import MagicMock

# Mocking AppState and streamlit session state for testing
class MockState:
    def __init__(self):
        self.current_project = "test_project"
        self.global_instructions = "Handle nulls as empty strings."
        self.kb_inventory = []
        self.fsdm_inventory = []
        self.v_manager = MagicMock()
        self.logs = []
        
        # Mock retriever
        self.retriever = MagicMock()
        self.v_manager.get_retriever.return_value = self.retriever
        self.retriever.invoke.return_value = [] # No docs for test

    def get_llm_config(self):
        return {
            "model_name": "gpt-4o", # Using gpt-4o for verification if possible, or dummy
            "api_key": os.getenv("OPENAI_API_KEY", "mock-key"),
            "base_url": None
        }

    def add_log(self, msg):
        self.logs.append(msg)
        print(f"LOG: {msg}")

def test_intent_generation():
    print("\n--- Testing Intent Generation ---")
    state = MockState()
    executor = AgentExecutor(state)
    
    row_data = {
        "row_idx": 1,
        "source_info": {
            "table_name": "users",
            "column_name": "first_name",
            "datatype": "VARCHAR"
        },
        "target_info": {
            "table_name": "dim_customer",
            "column_name": "cust_first_name",
            "datatype": "STRING"
        },
        "transformation_specs": {
            "type": "1:1",
            "condition": "None"
        }
    }
    
    insight = executor.generate_insight(row_data)
    print("\nGenerated Insight:")
    print(insight)
    
    assert "Intent:" in insight
    assert "Reasoning:" in insight
    assert "Pseudocode:" in insight

def test_mapping_generation():
    print("\n--- Testing Mapping Generation ---")
    state = MockState()
    executor = AgentExecutor(state)
    
    row_data = {
        "row_idx": 1,
        "source_info": {
            "table_name": "users",
            "column_name": "first_name",
            "datatype": "VARCHAR",
            "db_name": "source_db"
        },
        "target_info": {
            "table_name": "dim_customer",
            "column_name": "cust_first_name",
            "datatype": "STRING",
            "db_name": "target_db"
        },
        "transformation_specs": {
            "type": "1:1",
            "condition": "None"
        },
        "pre_mapping_insight": "**Intent:** 1:1 mapping from users.first_name to dim_customer.cust_first_name.\n\n**Reasoning:** Standard name mapping.\n\n**Pseudocode:**\n```sql\nSELECT first_name FROM users\n```"
    }
    
    # Mocking tool return values if needed, but the agent should be able to run
    # even with empty tools if the prompt is strong.
    
    result = executor.process_row(row_data, 1)
    print("\nMapping Result:")
    print(result)
    
    assert result["transformation_type"] != "ERROR"
    assert "transformation_logic" in result
    assert "reasoning" in result

if __name__ == "__main__":
    # Ensure we have an API key or mock it
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not set. Test might fail if it tries to call real LLM.")
    
    try:
        test_intent_generation()
        test_mapping_generation()
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
