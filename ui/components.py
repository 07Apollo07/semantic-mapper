import streamlit as st
import pandas as pd
from logic.model_fetcher import fetch_models
from logic import AppState

def sidebar_config():
    """Sidebar for configuration."""
    state = AppState()
    with st.sidebar:
        st.title("LLM Configuration")

        # Base URL and API Key
        base_url = st.text_input("Base URL", value=st.session_state.get("base_url", ""), placeholder="e.g. http://localhost:11434")
        api_key = st.text_input("API Key", value=st.session_state.get("api_key", ""), type="password")

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

        st.divider()
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

def step_indicator(current_step):
    # Initialize state to access sync method
    state = AppState()
    
    def on_step_change(target_step):
        state.sync()
        state.step = target_step

    steps = ["1. Knowledge Base", "2. Mapping & Preview", "3. Results", "4. Logs"]
    cols = st.columns(len(steps))
    for i, step_name in enumerate(steps):
        target = i + 1
        is_current = (target == current_step)
        
        cols[i].button(
            step_name, 
            key=f"step_btn_{target}", 
            use_container_width=True, 
            type="primary" if is_current else "secondary",
            on_click=on_step_change,
            args=(target,)
        )
    st.divider()

def display_logs(state, height=300, key_prefix="main"):
    """Reusable log display component."""
    st.subheader("Execution History 📑")
    logs_text = "\n".join(state.logs) if state.logs else "No logs yet."
    st.text_area(
        "Logs", 
        value=logs_text, 
        height=height, 
        disabled=True,
        key=f"{key_prefix}_logs_display_area"
    )
    
    col_l1, col_l2 = st.columns([1, 4])
    with col_l1:
        def on_clear_logs():
            state.clear_logs()
            state.sync()
        st.button("🧹 Clear Logs", on_click=on_clear_logs, type="secondary", use_container_width=True, key=f"{key_prefix}_clear_logs_btn")
    
    with col_l2:
        st.caption("Logs are persistent across steps.")
