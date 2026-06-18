import streamlit as st
import pandas as pd
from logic.model_fetcher import fetch_models
from logic import AppState
from streamlit_js import st_js
from agent.agents.agent_info import AGENT_INFO

def sidebar_config(state: AppState):
    """Sidebar for configuration."""
    with st.sidebar:
        st.title("LLM Configuration")

        # Base URL and API Key
        base_url = st.text_input("Base URL", value=st.session_state.get("base_url", ""), placeholder="e.g. http://localhost:11434")
        # api_key = st.text_input("API Key", value=st.session_state.get("api_key", ""), type="password", disabled=True)
        api_key = "Not Required"

        # Update session state
        st.session_state["base_url"] = base_url
        st.session_state["api_key"] = api_key

        # Model selection
        if st.button("Fetch Models"):
            if base_url:
                with st.spinner("Fetching models..."):
                    models = fetch_models(base_url, api_key)
                    if models:
                        st.session_state["available_models"] = models
                        st.success(f"Fetched {len(models)} models")
                    else:
                        st.error("Failed to fetch models. Check URL and API Key.")
            else:
                st.warning("Please enter a Base URL.")

        available_models = st.session_state.get("available_models", [])
        st.selectbox(
            "Select Model", 
            options=available_models, 
            index=0 if available_models and st.session_state.get("selected_model") in available_models else 0 if available_models else None,
            key="selected_model"
        )

        # ----- Agent Selector -----
        st.subheader("🤖 Agent Selection")
        # Build display options from AGENT_INFO keys
        agent_options = list(AGENT_INFO.keys())
        # Map to display names
        display_names = [AGENT_INFO[a]["display_name"] for a in agent_options]
        # Determine current selection index
        current_name = st.session_state.get("agent_name", "DEFAULT")
        try:
            current_idx = agent_options.index(current_name)
        except ValueError:
            current_idx = 0
        selected_display = st.selectbox(
            "Select Agent",
            options=display_names,
            index=current_idx,
            key="agent_selector"
        )
        # Map back to internal name
        selected_name = agent_options[display_names.index(selected_display)]
        if selected_name != st.session_state.get("agent_name"):
            st.session_state["agent_name"] = selected_name
            # Persist using the current state instance
            state.save_project()
            st.rerun()

        # Help expander showing description
        with st.expander("Agent Details"):
            info = AGENT_INFO.get(st.session_state.get("agent_name", "DEFAULT"), {})
            st.markdown(f"**{info.get('display_name', '')}**")
            st.markdown(info.get('description', ''))
            st.markdown("**Required Docs:** " + ", ".join(info.get('required_docs', [])))
            st.markdown("**Default Mappings:** " + info.get('default_mappings', ''))
            st.markdown(f"**Can Regenerate SQL:** {info.get('can_regen_sql', False)}")
            st.markdown(f"**Can Regenerate FSDM:** {info.get('can_regen_fsdm', False)}")

                # st.radio(   
        #     "Agent Mode",
        #     options=["One-shot", "ReAct Agent"],
        #     key="agent_mode",
        #     help="One-shot: Simple retrieval + generation. ReAct Agent: Can iteratively search KB if needed."
        # )
        st.session_state["agent_mode"] = "ReAct Agent"
        st.info("🤖 Agent Mode: ReAct (Always On)")
        st.subheader("Embedding Configuration")

        v_manager = state.v_manager
        if v_manager:
            st.write(f"**Model:** `{v_manager.model_name}`")
            if v_manager.embeddings:
                st.success("✅ Embedding model ready")
            else:
                if st.button("Download / Load Embedding Model"):
                    with st.spinner("Downloading/Loading model..."):
                        v_manager.load_model()
                        st.success("Model loaded!")
                        st.rerun()
                else:
                    st.info("Embedding model will load during KB submission.")

        st.divider()
        st.info("Ensure you have uploaded the Knowledge Base before submitting the mapping.")
        
        st.divider()
        if st.checkbox("🐞 Debug Mode", value=False):
            st.write("### Session State")
            st.json(st.session_state)

def display_logs(state: AppState, height=300, key_prefix="main"):
    """Reusable log display component that supports real-time updates and auto-scroll."""
    st.subheader("Execution History 📑")
    
    # Auto-scroll toggle
    col_t1, col_t2 = st.columns([1, 4])
    with col_t1:
        auto_scroll = st.checkbox("🔄 Auto-scroll", value=state.auto_scroll, key=f"{key_prefix}_auto_scroll_chk")
        if auto_scroll != state.auto_scroll:
            state.auto_scroll = auto_scroll
    
    # Placeholder for the logs
    log_placeholder = st.empty()
    
    def render_log_content():
        logs_text = "\n".join(state.logs) if state.logs else "No logs yet."
        with log_placeholder.container():
            st.text_area(
                "Logs", 
                value=logs_text, 
                height=height, 
                disabled=True
            )
            # if state.auto_scroll:
            #     # Force the textarea to scroll to the maximum possible scrollHeight
            #     st_js("""
            #         const textareas = parent.document.querySelectorAll('textarea');
            #         if (textareas.length > 0) {
            #             const last = textareas[textareas.length - 1];
            #             last.scrollTop = last.scrollHeight;
            #             // Forcing an extremely high value is a common trick to hit the absolute bottom
            #             last.scrollTop = 9999999;
            #         }
            #     """)

    # Initial render
    render_log_content()
    
    # Register the render function in session state so it can be called from anywhere
    st.session_state[f"{key_prefix}_log_renderer"] = render_log_content
    
    col_l1, col_l2 = st.columns([1, 4])
    with col_l1:
        def on_clear_logs():
            state.clear_logs()
            state.sync()
            st.rerun()
            
        st.button("🧹 Clear Logs", on_click=on_clear_logs, type="secondary", use_container_width=True, key=f"{key_prefix}_clear_logs_btn")
    
    with col_l2:
        st.caption("Logs are persistent across steps.")
    
    return log_placeholder
