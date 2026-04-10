import streamlit as st
from agent.agents.fsdm_agent import create_fsdm_discovery_agent
from agent.agents.agents_utils import FSDMDiscoveryState

def render_fsdm_test(state):
    """
    Test UI component to run the FSDM Discovery Agent for a selected row.
    """
    st.subheader("🧪 FSDM Discovery Agent Test")
    
    # Example input
    col_t1, col_t2 = st.columns(2)
    tbl = col_t1.text_input("Source Table", value="fsdm_accounts")
    col = col_t2.text_input("Source Column", value="AccountID")

    if st.button("Run FSDM Discovery Test"):
        with st.spinner("Agent discovery in progress..."):
            agent = create_fsdm_discovery_agent(
                model_name=state.selected_model,
                api_key=state.api_key,
                base_url=state.base_url,
                log_callback=lambda m: st.caption(m)
            )
            
            # Test input state
            test_state: FSDMDiscoveryState = {
                "source_info": {"table_name": tbl, "column_name": col},
                "target_info": {"table_name": "target_dim", "column_name": "target_id"},
                "fsdm_instructions": "Verify lineage and transformations.",
                "fsdm_lineage_intent": "",
                "fsdm_status": "",
                "messages": [],
                "project_name": state.current_project,
                "feedback": None
            }
            
            result = agent.invoke(test_state)
            st.success("Discovery Complete!")
            st.json(result)
