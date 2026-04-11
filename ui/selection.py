import streamlit as st
import pandas as pd
from typing import List, Dict, Any
from logic.project_manager import ProjectManager
from logic.state import AppState

def render_mapping_selection(state: AppState):
    """
    Renders an improved, styled hierarchical selection tree for mapping rows.
    Includes filtering controls and indicates partial table selection.
    """
    st.markdown("### 🎯 Mapping Selection")
    
    # 1. Load data
    df = ProjectManager.load_df_from_sql(state.current_project, "unified_mapping_view")
    if df.empty:
        st.info("No synced mappings available.")
        return

    df['_unique_id'] = df.apply(lambda r: f"{r['_src_file']}|{r['_src_sheet']}|{r.name}", axis=1)

    # 2. Filtering Controls
    st.markdown("#### 🔍 Filter Selection")
    c1, c2, c3 = st.columns(3)
    
    files = df["_src_file"].unique()
    
    # Use session state or persistent properties for filters
    sel_files = c1.multiselect("Filter by File", files, default=state.filter_files if state.filter_files else files)
    state.filter_files = sel_files
    
    df_filtered = df[df["_src_file"].isin(sel_files)]
    sheets = df_filtered["_src_sheet"].unique()
    
    sel_sheets = c2.multiselect("Filter by Sheet", sheets, default=state.filter_sheets if state.filter_sheets else sheets)
    state.filter_sheets = sel_sheets
    
    df_filtered = df_filtered[df_filtered["_src_sheet"].isin(sel_sheets)]
    tables = df_filtered["target_table"].unique()
    
    sel_tables = c3.multiselect("Filter by Table", tables, default=state.filter_tables if state.filter_tables else tables)
    state.filter_tables = sel_tables
    
    df_final = df_filtered[df_filtered["target_table"].isin(sel_tables)]
    state.save_project()

    # 3. State handling
    selected_ids = set(state.selected_mapping_rows)
    new_selected_ids = set()

    # 4. Render Tree
    for f_name in sel_files:
        f_df = df_final[df_final["_src_file"] == f_name]
        if f_df.empty: continue
        
        with st.expander(f"📁 **File:** {f_name}", expanded=True):
            sheets_in_file = f_df["_src_sheet"].unique()
            for s_name in sheets_in_file:
                s_df = f_df[f_df["_src_sheet"] == s_name]
                st.markdown(f"📄 **Sheet:** `{s_name}`")
                
                tables_in_sheet = s_df["target_table"].unique()
                for t_name in tables_in_sheet:
                    t_df = s_df[s_df["target_table"] == t_name]
                    t_ids = set(t_df["_unique_id"].tolist())
                    
                    # Logic for selection states
                    table_selected_ids = t_ids.intersection(selected_ids)
                    is_all_selected = len(table_selected_ids) == len(t_ids)
                    is_partially_selected = 0 < len(table_selected_ids) < len(t_ids)
                    
                    col1, col2 = st.columns([0.05, 0.95])
                    is_t_selected = col1.checkbox(f"sel_tbl_{t_name}", value=is_all_selected, key=f"sel_tbl_{f_name}_{s_name}_{t_name}", label_visibility="collapsed")
                    
                    # Visual feedback for partial selection
                    indicator = "⚠️" if is_partially_selected else ("✅" if is_all_selected else "🗄️")
                    col2.markdown(f"{indicator} **Target Table:** `{t_name}` — *{len(table_selected_ids)}/{len(t_df)} rows selected*")
                    
                    if is_t_selected:
                        new_selected_ids.update(t_ids)
                        
                    with st.expander("Show Rows", expanded=False):
                        for _, row in t_df.iterrows():
                            rid = row["_unique_id"]
                            r_label = f"Row {row.name}: `{row['source_column']}` → `{row['target_column']}`"
                            
                            is_r_selected = st.checkbox(r_label, value=(rid in selected_ids) or is_t_selected, key=f"sel_row_{rid}")
                            if is_r_selected:
                                new_selected_ids.add(rid)
                            elif rid in new_selected_ids and not is_t_selected:
                                new_selected_ids.remove(rid)

    # 5. Update
    if new_selected_ids != selected_ids:
        print(f"[DEBUG] Selection changed: {len(new_selected_ids)} rows.")
        print(f"[DEBUG] Selected IDs: {list(new_selected_ids)}")
        state.selected_mapping_rows = list(new_selected_ids)
        state.save_project()
        st.rerun()

    st.divider()
    st.success(f"**Total Selected Rows:** {len(state.selected_mapping_rows)}")

def render_fsdm_discovery_ui(state: AppState):
    """
    Renders the FSDM Discovery UI for executing the first agentic phase.
    """
    from agent.test_agents.test_fsdm import render_fsdm_test
    st.divider()
    st.markdown("### 🧠 Phase 1: FSDM Discovery")
    render_fsdm_test(state)
