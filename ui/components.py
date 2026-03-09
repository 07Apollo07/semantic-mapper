import streamlit as st
import pandas as pd
from logic.model_fetcher import fetch_models

def sidebar_config():
    """Sidebar for configuration."""
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
                        print(models)
                        st.session_state["available_models"] = models
                        st.success(f"Fetched {len(models)} models")
                    else:
                        st.error("Failed to fetch models. Check URL and API Key.")
            else:
                st.warning("Please enter a Base URL.")

        available_models = st.session_state.get("available_models", [])
        selected_model = st.selectbox(
            "Select Model", 
            options=available_models, 
            index=0 if available_models else None,
            key="selected_model"
        )

        st.divider()
        st.subheader("Embedding Configuration")

        # Local Embedding Model Status
        v_manager = st.session_state.get("v_manager")
        if v_manager:
            st.write(f"**Model:** `{v_manager.model_name}`")
            if v_manager.embeddings:
                st.success("✅ Embedding model ready")
            else:
                if st.button("Download / Load Embedding Model"):
                    with st.spinner("Downloading/Loading model... (this may take a while)"):
                        v_manager.load_model()
                        st.success("Model loaded!")
                        st.rerun()
                else:
                    st.info("Embedding model not loaded yet. It will load automatically during KB submission.")

        st.divider()
        st.info("Ensure you have uploaded the Knowledge Base before submitting the mapping.")

def step_indicator(current_step):
    steps = ["1. Knowledge Base", "2. Mapping Config", "3. Preview & Run", "4. Results"]
    cols = st.columns(len(steps))
    for i, step in enumerate(steps):
        if i + 1 == current_step:
            cols[i].button(step, key=f"step_{i+1}", use_container_width=True, type="primary")
        else:
            if cols[i].button(step, key=f"step_{i+1}", use_container_width=True):
                st.session_state.step = i + 1
                st.rerun()
    st.divider()

def display_mapping_row(row_idx, row_data, on_regenerate):
    """Displays a single result row with transformation and a regenerate button."""
    with st.container():
        c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 2, 1])
        with c1:
            st.write(f"Row {row_idx}")
        with c2:
            st.markdown(f"**Type:** {row_data.get('transformation_type', 'N/A')}")
        with c3:
            st.markdown(f"**Logic:** {row_data.get('transformation_logic', 'N/A')}")
        with c4:
            st.markdown(f"**Reasoning:** {row_data.get('reasoning', 'N/A')}")
        with c5:
            if st.button("Regenerate", key=f"reg_{row_idx}"):
                on_regenerate(row_idx)
    st.divider()
