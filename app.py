import streamlit as st
import pandas as pd
import io
from logic import (
    get_excel_sheets, 
    excel_col_to_idx,
    AppState,
    ProjectManager
)
from logic.db.service import DBService
from logic.mapping.config import MappingConfig
from logic.mapping.service import MappingService
from logic.utils import get_cell_value
from agent.agents.executor import AgentExecutor
from agent.agents.mapping_table_group_agent import mapping_table_group_agent
from agent.agents.fsdm_metadata import generate_metadata
from agent.tools.tools import sample_table_data_logic
from ui import sidebar_config, display_logs, render_mapping_selection, render_fsdm_discovery_ui
# from agent.agents.test_fsdm import render_fsdm_test

st.set_page_config(page_title="Semantic Mapper AI", layout="wide")

#  Initialize State
state = AppState()

#  --- Project Selection ---
if not state.current_project:
    st.title("Semantic Mapper AI 🧠")
    st.markdown("### Select or Create a Project")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Create New Project")
        new_proj_name = st.text_input("Project Name")
        if st.button("Create Project", type="primary"):
            if new_proj_name:
                if ProjectManager.create_project(new_proj_name):
                    state.load_project(new_proj_name)
                    st.rerun()
                else:
                    st.error("Project already exists.")
            else:
                st.error("Please enter a project name.")
    
    with col2:
        st.subheader("Open Existing Project")
        projects = ProjectManager.list_projects()
        if projects:
            selected_proj = st.selectbox("Select Project", projects)
            col_open, col_del = st.columns([1, 1])
            if col_open.button("Open Project", type="primary", width='stretch'):
                state.load_project(selected_proj)
                st.rerun()
                
            if col_del.button("Delete Project", type="secondary", width='stretch'):
                 ProjectManager.delete_project(selected_proj)
                 st.success(f"Deleted project: {selected_proj}")
                 st.rerun()
        else:
            st.info("No projects found.")
            
    st.stop() 

#  --- Main App ---

#  Project Sidebar
with st.sidebar:
    st.markdown(f"### 📂 Project: {state.current_project}")
    if st.button("↩️ Switch Project", width='stretch'):
        state.current_project = None
        state.reset_kb()
        st.rerun()
    st.divider()

sidebar_config(state)
st.title("Semantic Mapper AI 🧠")

#  Section 1: Knowledge Base Manager
st.header("1.1 Semantic Manager")

#  --- 1. Upload Section ---
uploaded_files = st.file_uploader("Upload PDFs or Excel Sheets", accept_multiple_files=True, type=["pdf", "xlsx"], key="uploader")

if uploaded_files:
    inventory = state.kb_inventory
    for f in uploaded_files:
        if not any(item["name"] == f.name for item in inventory):
            f.seek(0)
            file_bytes = f.read()
            
            # Save to disk
            ProjectManager.save_file(state.current_project, f.name, file_bytes, sub_dir="files/semantic")
            
            if f.name.endswith(".pdf"):
                inventory.append({
                    "name": f.name,
                    "type": "pdf",
                    "bytes": file_bytes,
                    "selected": True, 
                    "indexed": False  
                })
            elif f.name.endswith(".xlsx"):
                sheets = get_excel_sheets(file_bytes)
                inventory.append({
                    "name": f.name,
                    "type": "excel",
                    "bytes": file_bytes,
                    "sheets": {s: {"selected": True, "indexed": False, "metadata": ""} for s in sheets}
                })
    state.kb_inventory = inventory # Trigger update
    state.save_project()

#  --- 2. Dashboard Section ---
if state.kb_inventory:
    st.subheader("Manage Documents")
    needs_sync = False
    inventory = state.kb_inventory
    
    for idx, item in enumerate(inventory):
        with st.container():
            col_name, col_status, col_rm = st.columns([5, 2, 1])
            
            if item["type"] == "pdf":
                if item["indexed"] and item["selected"]:
                    col_status.success("✅ Indexed")
                elif not item["indexed"] and item["selected"]:
                    col_status.warning("⏳ Pending")
                    needs_sync = True
                elif item["indexed"] and not item["selected"]:
                    col_status.info("🗑️ To Remove")
                    needs_sync = True
                
                new_sel = col_name.checkbox(f"📄 {item['name']}", value=item['selected'], key=f"sel_pdf_{idx}")
                if new_sel != item["selected"]:
                    inventory[idx]["selected"] = new_sel
                    state.kb_inventory = inventory
                    state.save_project()
                    st.rerun()

            else: # Excel
                sheets_data = item["sheets"]
                # Track indexing status based on SQL and Vector presence
                indexed_sql_count = sum(1 for s in sheets_data.values() if s.get("indexed_sql"))
                indexed_vec_count = sum(1 for s in sheets_data.values() if s.get("indexed_vector"))
                selected_count = sum(1 for s in sheets_data.values() if s["selected"])
                
                # Sync needs to happen if selected items are not yet indexed in both
                needs_sync = any(
                    s["selected"] and (not s.get("indexed_sql") or not s.get("indexed_vector")) 
                    for s in sheets_data.values()
                )
                # Also needs sync if previously indexed items were deselected
                if not needs_sync:
                     needs_sync = any(
                        not s["selected"] and (s.get("indexed_sql") or s.get("indexed_vector"))
                        for s in sheets_data.values()
                    )

                if indexed_sql_count == selected_count and indexed_vec_count == selected_count and selected_count > 0:
                    col_status.success(f"✅ Synced")
                elif selected_count > 0 or needs_sync:
                    col_status.info(f"⏳ Pending")
                    needs_sync = True

                col_name.markdown(f"📊 **{item['name']}**")
                with col_name.expander("Show Sheets"):
                    for s_name, s_info in sheets_data.items():
                        s_col1, s_col2, s_col3 = st.columns([3, 1, 1])
                        checked = s_col1.checkbox(f"{s_name}", value=s_info["selected"], key=f"sel_semantic_{item['name']}_{s_name}_{idx}")
                        if checked != s_info["selected"]:
                            inventory[idx]["sheets"][s_name]["selected"] = checked
                            state.kb_inventory = inventory
                            state.save_project()
                            st.rerun()

                        if s_info.get("indexed_sql") and s_info.get("indexed_vector"):
                            s_col2.markdown(":green[✅ In DB/Vec]")
                            s_col3.checkbox("Merge Headers", value=s_info.get("combine_headers", False), key=f"merge_locked_semantic_{item['name']}_{s_name}_{idx}", disabled=True)
                            
                            # Metadata Management
                            with st.expander("⚙️ Metadata"):
                                current_meta = s_info.get("metadata", "")
                                if st.button("✨ Generate Metadata", key=f"gen_meta_semantic_{item['name']}_{s_name}_{idx}"):
                                    with st.spinner("Analyzing data..."):
                                        table_name = ProjectManager.get_sanitized_table_name("semantic_fsdm_" + s_name)
                                        sample_df = sample_table_data_logic(table_name, state.current_project)
                                        print(sample_df)
                                        s_info["metadata"] = generate_metadata(
                                            sample_df, state.selected_model, state.api_key, state.base_url
                                        )
                                        state.save_project()
                                        st.rerun()
                                            
                                new_val = st.text_area(
                                    "Table Definitions/Instructions", 
                                    value=s_info.get("metadata", ""), 
                                    key=f"meta_semantic_{item['name']}_{s_name}_{hash(s_info.get('metadata', ''))}_{idx}"
                                )
                                if new_val != s_info.get("metadata", ""):
                                    s_info["metadata"] = new_val
                                    state.save_project()
                                    st.rerun()
                        
                        elif s_info.get("selected"):
                            # Header Merge
                            merge_check = s_col3.checkbox("Merge Headers", value=s_info.get("combine_headers", False), key=f"merge_semantic_{item['name']}_{s_name}_{idx}")
                            if merge_check != s_info.get("combine_headers", False):
                                s_info["combine_headers"] = merge_check
                                state.save_project()
                                st.rerun()
            if col_rm.button("🗑️", key=f"del_file_{idx}"):
                # Use unified cleanup
                ProjectManager.cleanup_resources(state.current_project, item, state.semantic_service, DBService, prefix="semantic_fsdm_")
                
                # Remove from disk
                ProjectManager.delete_file(state.current_project, item["name"], sub_dir="files/semantic")
                
                inventory.pop(idx)
                state.kb_inventory = inventory
                state.save_project()
                st.rerun()
        st.divider()

    # --- 3. Action Buttons ---
    col_btn1, col_btn2 = st.columns([1, 1])
    if needs_sync:
        if col_btn1.button("🔄 Sync with Vector & DB", type="primary", width='stretch'):
            with st.spinner("Syncing to Vector Store and SQLite..."):
                for idx, item in enumerate(inventory):
                    inventory[idx] = ProjectManager.sync_to_storage(
                        state.current_project, item, state.semantic_service, DBService, prefix="semantic_fsdm_"
                    )
                
                state.kb_inventory = inventory
                state.save_project()
                st.success("Vector Store & DB updated!")
                st.rerun()
    
    if col_btn2.button("🧹 Clear All", width='stretch'):
        state.reset_kb()
        state.save_project()
        st.rerun()

st.divider()

#  Section 1.2: Knowledge Base DB Manager
st.header("1.2 ETL Manager")

#  --- 1. Upload Section ---
fsdm_uploaded_files = st.file_uploader("Upload FSDM/ETL Excel Sheets", accept_multiple_files=True, type=["xlsx"], key="fsdm_uploader")

if fsdm_uploaded_files:
    fsdm_inventory = state.fsdm_inventory
    for f in fsdm_uploaded_files:
        if not any(item["name"] == f.name for item in fsdm_inventory):
            f.seek(0)
            file_bytes = f.read()
            
            # Save to disk
            ProjectManager.save_file(state.current_project, f.name, file_bytes, sub_dir="files/fsdm")
            
            sheets = get_excel_sheets(file_bytes)
            fsdm_inventory.append({
                "name": f.name,
                "type": "excel",
                "bytes": file_bytes,
                "sheets": {s: {"selected": True, "indexed": False, "metadata": ""} for s in sheets}
            })
    state.fsdm_inventory = fsdm_inventory # Trigger update
    state.save_project()

#  --- 2. Dashboard Section ---
if state.fsdm_inventory:
    st.subheader("Manage DB Documents")
    needs_db_sync = False
    fsdm_inventory = state.fsdm_inventory
    
    for idx, item in enumerate(fsdm_inventory):
        with st.container():
            col_name, col_status, col_rm = st.columns([5, 2, 1])
            
            sheets_data = item["sheets"]
            # Check for existing sync status in both DB and Vector
            indexed_sql_count = sum(1 for s in sheets_data.values() if s.get("indexed_sql"))
            indexed_vec_count = sum(1 for s in sheets_data.values() if s.get("indexed_vector"))
            selected_count = sum(1 for s in sheets_data.values() if s["selected"])
            
            # Sync needs to happen if selected items are not yet indexed in both
            needs_db_sync = any(
                s["selected"] and (not s.get("indexed_sql") or not s.get("indexed_vector")) 
                for s in sheets_data.values()
            )
            # Also needs sync if previously indexed items were deselected
            if not needs_db_sync:
                 needs_db_sync = any(
                    not s["selected"] and (s.get("indexed_sql") or s.get("indexed_vector"))
                    for s in sheets_data.values()
                )

            if indexed_sql_count == selected_count and indexed_vec_count == selected_count and selected_count > 0:
                col_status.success(f"✅ Synced")
            elif selected_count > 0 or needs_db_sync:
                col_status.info(f"⏳ Pending")
                needs_db_sync = True
            
            # Also needs sync if previously indexed items were deselected
            if not needs_db_sync:
                 needs_db_sync = any(
                    not s["selected"] and (s.get("indexed_sql") or s.get("indexed_vector"))
                    for s in sheets_data.values()
                )

            col_name.markdown(f"📊 **{item['name']}**")
            with col_name.expander("Show Sheets"):
                for s_name, s_info in sheets_data.items():
                    s_col1, s_col2, s_col3 = st.columns([3, 1, 1])
                    checked = s_col1.checkbox(f"{s_name}", value=s_info["selected"], key=f"sel_fsdm_{item['name']}_{s_name}_{idx}")
                    if checked != s_info["selected"]:
                        fsdm_inventory[idx]["sheets"][s_name]["selected"] = checked
                        state.fsdm_inventory = fsdm_inventory
                        state.save_project()
                        st.rerun()
                    if s_info.get("indexed_sql") and s_info.get("indexed_vector"):
                        s_col2.markdown(":green[✅ In DB/Vec]")
                        s_col3.checkbox("Merge Headers", value=s_info.get("combine_headers", False), key=f"merge_locked_fsdm_{item['name']}_{s_name}_{idx}", disabled=True)
                        
                        # Metadata Management
                        with st.expander("⚙️ Metadata"):
                            # Read directly from state
                            current_meta = state.fsdm_inventory[idx]["sheets"][s_name].get("metadata", "")
                            if st.button("✨ Generate Metadata", key=f"gen_meta_fsdm_{item['name']}_{s_name}_{idx}"):
                                with st.spinner("Analyzing data..."):
                                    table_name = ProjectManager.get_sanitized_table_name("FSDM/ETL_" + s_name)
                                    sample_df = sample_table_data_logic(table_name, state.current_project)
                                    print(sample_df)
                                    new_meta = generate_metadata(
                                        sample_df, 
                                        state.selected_model, 
                                        state.api_key, 
                                        state.base_url
                                    )
                                    state.fsdm_inventory[idx]["sheets"][s_name]["metadata"] = new_meta
                                    state.save_project()
                                    st.rerun()
                                    
                            # Use a key that incorporates the hash of the metadata to force re-render when it changes
                            new_val = st.text_area(
                                "Table Definitions/Instructions", 
                                value=current_meta, 
                                key=f"meta_fsdm_{item['name']}_{s_name}_{hash(current_meta)}_{idx}"
                            )
                            if new_val != current_meta:
                                state.fsdm_inventory[idx]["sheets"][s_name]["metadata"] = new_val
                                state.save_project()
                                st.rerun()
                                
                    elif s_info["selected"]:
                        merge_check = s_col3.checkbox("Merge Headers", value=s_info.get("combine_headers", False), key=f"merge_fsdm_{item['name']}_{s_name}_{idx}")
                        if merge_check != s_info.get("combine_headers", False):
                            fsdm_inventory[idx]["sheets"][s_name]["combine_headers"] = merge_check
                            state.fsdm_inventory = fsdm_inventory
                            state.save_project()
                            st.rerun()
            
            if col_rm.button("🗑️", key=f"del_fsdm_file_{idx}"):
                # Use unified cleanup
                ProjectManager.cleanup_resources(state.current_project, item, state.fsdm_service, DBService, prefix="fsdm_etl_")

                # Remove from disk
                ProjectManager.delete_file(state.current_project, item["name"], sub_dir="files/fsdm")
                
                fsdm_inventory.pop(idx)
                state.fsdm_inventory = fsdm_inventory
                state.save_project()
                st.rerun()
        st.divider()

    # --- 3. Action Buttons ---
    if needs_db_sync:
        if st.button("🗄️ Sync Tables & Vector", type="primary", width='stretch'):
            with st.spinner("Syncing to SQLite and Vector Store..."):
                for idx, item in enumerate(fsdm_inventory):
                    fsdm_inventory[idx] = ProjectManager.sync_to_storage(
                        state.current_project, item, state.fsdm_service, DBService, prefix="fsdm_etl_"
                    )
                
                state.fsdm_inventory = fsdm_inventory
                state.save_project()
                st.success("SQLite & Vector Store updated!")
                st.rerun()

st.divider()

# Section 2: Mapping Configuration
st.header("2. Configure Mapping Documents")

# --- Instructions Management ---
st.subheader("⚙️ System Instructions")
col_g, col_f, col_m = st.columns([2, 1, 1])

# Fetch current instructions
current_global = ProjectManager.get_instructions(state.current_project, 'global')
current_fsdm = ProjectManager.get_instructions(state.current_project, 'fsdm')
current_mapping = ProjectManager.get_instructions(state.current_project, 'mapping')

with st.container():
    global_instr = st.text_area("Global Instructions (Style, Tone, Standards)", value=current_global, height=100)

    col_f1, col_m1 = st.columns(2)
    with col_f1:
        fsdm_instr = st.text_area("FSDM Discovery Instructions", value=current_fsdm, height=100)
    with col_m1:
        mapping_instr = st.text_area("Mapping Generation Instructions", value=current_mapping, height=100)

    if st.button("💾 Save All Instructions"):
        ProjectManager.save_instructions(state.current_project, 'global', global_instr)
        ProjectManager.save_instructions(state.current_project, 'fsdm', fsdm_instr)
        ProjectManager.save_instructions(state.current_project, 'mapping', mapping_instr)
        st.success("Instructions saved to database!")

# --- 1. Multi-File Uploader ---
mapping_files = st.file_uploader("Upload Mapping Excel Sheets", accept_multiple_files=True, type=["xlsx"], key="map_uploader")


if mapping_files:
    inventory = state.mapping_inventory or []
    # Inventory update logic
    for f in mapping_files:
        if not any(item["name"] == f.name for item in inventory):
            f.seek(0)
            file_bytes = f.read()
            ProjectManager.save_file(state.current_project, f.name, file_bytes, sub_dir="files/mapping")
            
            sheets = get_excel_sheets(file_bytes)
            inventory.append({
                "name": f.name,
                "sheets": {s: {"selected": False, "config": MappingConfig().__dict__} for s in sheets}
            })
    state.mapping_inventory = inventory
    state.save_project()

# --- 2. Mapping Dashboard ---
if state.mapping_inventory:
    st.subheader("Manage Mapping Sheets")
    
    for idx, item in enumerate(state.mapping_inventory):
        with st.expander(f"📁 {item['name']}", expanded=False):
            for s_name, s_info in item["sheets"].items():
                s_col1, s_col2 = st.columns([3, 1])
                checked = s_col1.checkbox(f"{s_name}", value=s_info["selected"], key=f"sel_map_{item['name']}_{s_name}")
                
                # Sync status indicator
                status = s_info.get("sync_status", "Pending")
                s_col2.caption(f"Status: {status}")

                if checked != s_info["selected"]:
                    state.mapping_inventory[idx]["sheets"][s_name]["selected"] = checked
                    state.save_project()
                    st.rerun()
                
                if checked:
                    with st.expander(f"⚙️ Config for {s_name}"):
                        cfg = s_info["config"]
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown("### Target Columns (Semantic)")
                            cfg["target_fields"]["subj"] = st.text_input("Target Subject Area", value=cfg["target_fields"]["subj"], key=f"t_subj_{item['name']}_{s_name}")
                            cfg["target_fields"]["db"] = st.text_input("Target DB Name", value=cfg["target_fields"]["db"], key=f"t_db_{item['name']}_{s_name}")
                            cfg["target_fields"]["tbl"] = st.text_input("Target Table Name", value=cfg["target_fields"]["tbl"], key=f"t_tbl_{item['name']}_{s_name}")
                            cfg["target_fields"]["col"] = st.text_input("Target Column Name", value=cfg["target_fields"]["col"], key=f"t_col_{item['name']}_{s_name}")
                            cfg["target_fields"]["type"] = st.text_input("Target Datatype", value=cfg["target_fields"]["type"], key=f"t_type_{item['name']}_{s_name}")

                        with col2:
                            st.markdown("### Source Columns (FSDM)")
                            cfg["source_fields"]["subj"] = st.text_input("Subject Area Column", value=cfg["source_fields"]["subj"], key=f"s_subj_{item['name']}_{s_name}")
                            cfg["source_fields"]["db"] = st.text_input("DB Name Column", value=cfg["source_fields"]["db"], key=f"s_db_{item['name']}_{s_name}")
                            cfg["source_fields"]["tbl"] = st.text_input("Table Name Column", value=cfg["source_fields"]["tbl"], key=f"s_tbl_{item['name']}_{s_name}")
                            cfg["source_fields"]["col"] = st.text_input("Column Name Column", value=cfg["source_fields"]["col"], key=f"s_col_{item['name']}_{s_name}")
                            cfg["source_fields"]["type"] = st.text_input("Datatype Column", value=cfg["source_fields"]["type"], key=f"s_type_{item['name']}_{s_name}")
                        
                        with col3:
                            st.markdown("### Physical Source Definitions")
                            # Add physical source config to cfg if not present
                            if "physical_source_fields" not in cfg:
                                cfg["physical_source_fields"] = {"subj": "", "db": "", "tbl": "", "col": "", "type": ""}
                                
                            cfg["physical_source_fields"]["subj"] = st.text_input("Phys. Subject Area", value=cfg["physical_source_fields"]["subj"], key=f"p_subj_{item['name']}_{s_name}")
                            cfg["physical_source_fields"]["db"] = st.text_input("Phys. DB Name", value=cfg["physical_source_fields"]["db"], key=f"p_db_{item['name']}_{s_name}")
                            cfg["physical_source_fields"]["tbl"] = st.text_input("Phys. Table Name", value=cfg["physical_source_fields"]["tbl"], key=f"p_tbl_{item['name']}_{s_name}")
                            cfg["physical_source_fields"]["col"] = st.text_input("Phys. Column Name", value=cfg["physical_source_fields"]["col"], key=f"p_col_{item['name']}_{s_name}")
                            cfg["physical_source_fields"]["type"] = st.text_input("Phys. Datatype", value=cfg["physical_source_fields"]["type"], key=f"p_type_{item['name']}_{s_name}")
                        
                        st.subheader("Transformation Specs")
                        c_tr1, c_tr2, c_tr3, c_tr4 = st.columns(4)
                        cfg["trans_fields"]["type"] = c_tr1.text_input("Transf. Type Column", value=cfg["trans_fields"]["type"], key=f"tr_type_{item['name']}_{s_name}")
                        cfg["trans_fields"]["cond"] = c_tr2.text_input("Transf. Condition Column", value=cfg["trans_fields"]["cond"], key=f"tr_cond_{item['name']}_{s_name}")
                        cfg["trans_fields"]["remarks"] = c_tr3.text_input("Remarks Column", value=cfg["trans_fields"]["remarks"], key=f"tr_remarks_{item['name']}_{s_name}")
                        cfg["data_start_row"] = c_tr4.number_input("Data Row Start (1-based)", min_value=1, value=cfg.get("data_start_row", 1), key=f"dr_start_{item['name']}_{s_name}")

                        if st.button("Save & Preview", key=f"save_{item['name']}_{s_name}"):
                            state.mapping_inventory[idx]["sheets"][s_name]["config"] = cfg
                            state.mapping_inventory[idx]["sheets"][s_name]["sync_status"] = "Pending"
                            state.save_project()
                            # Perform individual sync
                            try:
                                MappingService.sync_sheet(state.current_project, item, s_name)
                                state.mapping_inventory[idx]["sheets"][s_name]["sync_status"] = "Synced"
                                state.save_project()
                                st.success(f"Synced {s_name} to DB!")
                            except Exception as e:
                                st.error(f"Sync failed: {e}")
                            st.rerun()

                        # Always try to fetch preview from DB if table exists (moved inside expander)
                        try:
                            tbl_name = ProjectManager.get_sanitized_table_name(f"mapping_{item['name']}_{s_name}")
                            preview_df = ProjectManager.load_df_from_sql(state.current_project, tbl_name)
                            if not preview_df.empty:
                                st.write("##### Table Preview (DB)")
                                st.dataframe(preview_df.head(5))
                        except:
                            pass

    if st.button("🔄 Sync Mappings to Master", type="primary", use_container_width=True):
        with st.spinner("Syncing to Master Mapping Table..."):
            MappingService.sync_mappings(state.current_project, state.mapping_inventory)
            st.success("Master Mapping table updated!")
            st.rerun()

else:
    st.info("Please upload one or more Mapping Excel files to begin.")

# Add the new selection tree here
render_mapping_selection(state)

st.divider()
col_gen, col_stop = st.columns(2)

if state.processing_mode == "Row":
    btn_label = f"🚀 Generate Row Mappings ({len(state.selected_mapping_rows)} rows)" if len(state.selected_mapping_rows) > 0 else "🚀 Generate Row Mappings"
    if col_gen.button(btn_label, type="primary", use_container_width=True, disabled=len(state.selected_mapping_rows) == 0 or state.mapping_active):
        state.mapping_active = True
        state.mapping_idx = 0 
        state.save_project()
        st.rerun()
elif state.processing_mode == "Table":
    btn_label = f"🚀 Generate Table Mappings ({len(state.filter_tables)} tables)" if len(state.filter_tables) > 0 else "🚀 Generate Table Mappings"
    if col_gen.button(btn_label, type="primary", use_container_width=True, disabled=len(state.filter_tables) == 0 or state.mapping_active):
        state.mapping_active = True
        state.save_project()
        st.rerun()

with col_stop:
    if st.button("🛑 Stop Mapping", type="secondary", use_container_width=True, disabled=not state.mapping_active):
        state.mapping_active = False
        state.save_project()
        st.rerun()

st.divider()


# Section 3: Results
st.header("3. Transformation Results")

# Processing Mode Toggle
mode = st.radio("Processing Mode", ["Row", "Table"], horizontal=True, index=0 if state.processing_mode == "Row" else 1)
if mode != state.processing_mode:
    state.processing_mode = mode
    state.save_project()
    st.rerun()

# Pull results from DB
if state.processing_mode == "Row":
    available_tables = ProjectManager.get_unique_target_tables(state.current_project)
    if available_tables:
        # Use a selectbox to pick which table to view results for
        selected_view_table = st.selectbox(
            "Select Target Table to view results", 
            available_tables, 
            index=available_tables.index(state.selected_target_table) if state.selected_target_table in available_tables else 0
        )
        if selected_view_table != state.selected_target_table:
            state.selected_target_table = selected_view_table
            st.rerun()

        db_results = ProjectManager.get_mappings_by_table(state.current_project, state.selected_target_table)
        # Only show those with logic generated
        completed_results = [r for r in db_results if r.get('transformation_logic')]
    else:
        completed_results = []

    if not completed_results:
        st.info("No SQL transformations generated yet for this table. Complete Step 2.5 above.")
    else:
        st.write(f"Showing {len(completed_results)} mappings for `{state.selected_target_table}`.")

        for res in completed_results:
            row_idx = res['row_idx']
            with st.container(border=True):
                # Header: Row + Type + SQL
                col_l, col_r = st.columns([1, 4])
                with col_l:
                    st.markdown(f"**Row #{row_idx}**")
                    st.caption(f"`{res['transformation_type']}`")
                
                    # Visual check for verified SQL
                    if res.get('validation_status') == 'SQL Verified':
                        st.success("Verified")
                    else:
                        st.info("Draft")

                with col_r:
                    st.code(res['transformation_logic'], language="sql")
            
                # Compact Metadata
                s = res['source_info']
                t = res['target_info']
                st.caption(f"**Src:** `{s.get('db_name')}.{s.get('table_name')}.{s.get('column_name')}` | **Tgt:** `{t.get('db_name')}.{t.get('table_name')}.{t.get('column_name')}`")

                # Details Expander
                with st.expander("Details, Reasoning & Feedback", expanded=False):
                    # 1. FSDM Discovery Intelligence (Phase 1)
                    st.markdown("#### 🧠 Phase 1: FSDM Discovery Intelligence")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Findings:**\n{res.get('fsdm_findings', 'N/A')}")
                    with c2:
                        st.markdown(f"**Recommended Sources:**\n`{res.get('fsdm_recommended_sources', 'N/A')}`")
                    
                    st.markdown(f"**Discovery Reasoning:**\n{res.get('fsdm_reasoning', 'N/A')}")
                    st.markdown(f"**Discovery Report (Full):**\n{res.get('fsdm_intent', 'N/A')}")
                    
                    st.divider()

                    # 2. SQL Engineering (Phase 2)
                    st.markdown("#### ⚙️ Phase 2: SQL Engineering")
                    st.markdown(f"**Mapping Reasoning:**\n{res.get('reasoning', 'N/A')}")
                
                    # SQL Verification Toggle
                    current_v_status = res.get('validation_status', 'Mapping Complete')
                    sql_is_verified = st.toggle("Verify SQL (Golden Example)", value=(current_v_status == 'SQL Verified'), key=f"sql_v_{row_idx}")
                
                    if sql_is_verified and current_v_status != 'SQL Verified':
                        ProjectManager.update_mapping_validation(state.current_project, row_idx, {"validation_status": "SQL Verified"})
                        st.rerun()
                    elif not sql_is_verified and current_v_status == 'SQL Verified':
                        ProjectManager.update_mapping_validation(state.current_project, row_idx, {"validation_status": "Mapping Complete"})
                        st.rerun()

                    feedback = st.text_area("Feedback", value=st.session_state.get(f"feed_{row_idx}", ""), key=f"feed_{row_idx}", disabled=sql_is_verified)
                
                    def on_regen_fsdm(idx, row_data):
                        feed = st.session_state.get(f"feed_{idx}", "")
                        state.sync()
                        with st.spinner(f"Regenerating FSDM for row {idx}..."):
                            executor = AgentExecutor(state)
                            new_fsdm = executor.process_fsdm_only(row_data, idx, feedback=feed)
                            # Update DB with new FSDM intent
                            ProjectManager.update_mapping_row(state.current_project, idx, {
                                "fsdm_intent": new_fsdm.get("fsdm_intent", {}).get("lineage_intent", ""),
                                "fsdm_findings": new_fsdm.get("fsdm_intent", {}).get("findings", ""),
                                "fsdm_reasoning": new_fsdm.get("fsdm_intent", {}).get("reasoning", ""),
                                "fsdm_recommended_sources": new_fsdm.get("fsdm_intent", {}).get("recommended_sources", []),
                                "fsdm_status": new_fsdm.get("fsdm_status")
                            })

                    def on_regen_sql(idx, row_data):
                        feed = st.session_state.get(f"feed_{idx}", "")
                        state.sync()
                        with st.spinner(f"Regenerating SQL for row {idx}..."):
                            executor = AgentExecutor(state)
                            # We need to make sure row_data has the latest fsdm_intent from DB
                            latest_row = ProjectManager.get_mapping_by_row(state.current_project, idx)
                            row_data['fsdm_intent'] = {
                                "lineage_intent": latest_row.get('fsdm_intent'),
                                "findings": latest_row.get('fsdm_findings'),
                                "reasoning": latest_row.get('fsdm_reasoning'),
                                "recommended_sources": latest_row.get('fsdm_recommended_sources') or []
                            }
                            new_res = executor.process_mapping_only(row_data, idx, feedback=feed)
                            ProjectManager.update_mapping_row(state.current_project, idx, new_res)
                
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("🔄 Regenerate FSDM", key=f"btn_fsdm_{row_idx}", on_click=on_regen_fsdm, args=(row_idx, res), disabled=sql_is_verified, use_container_width=True):
                        st.rerun()
                    if c_btn2.button("⚙️ Regenerate SQL", key=f"btn_sql_{row_idx}", on_click=on_regen_sql, args=(row_idx, res), disabled=sql_is_verified, use_container_width=True):
                        st.rerun()

        # Export all tables from DB
        if st.button("📦 Export All Processed Tables to Excel", width='stretch'):
            all_db_data = []
            unique_tables = ProjectManager.get_unique_target_tables(state.current_project)
            for tbl in unique_tables:
                tbl_mappings = ProjectManager.get_mappings_by_table(state.current_project, tbl)
                for m in tbl_mappings:
                    if m.get('transformation_logic'):
                        s = m['source_info']
                        t = m['target_info']
                        all_db_data.append({
                            "Target Table": m['target_table'],
                            "Row": m['row_idx'],
                            "Source Subject Area": s.get('subject_area'),
                            "Source DB Name": s.get('db_name'),
                            "Source Table Name": s.get('table_name'),
                            "Source Column Name": s.get('column_name'),
                            "Source Datatype": s.get('datatype'),
                            "Target Subject Area": t.get('subject_area'),
                            "Target DB Name": t.get('db_name'),
                            "Target Table Name": t.get('table_name'),
                            "Target Column Name": t.get('column_name'),
                            "Target Datatype": t.get('datatype'),
                            "Transformation Type": m['transformation_type'],
                            "Transformation Logic": m['transformation_logic'],
                            "SQL Reasoning": m['reasoning'],
                            "FSDM Findings": m.get('fsdm_findings'),
                            "FSDM Reasoning": m.get('fsdm_reasoning'),
                            "FSDM Recommended Sources": m.get('fsdm_recommended_sources'),
                            "FSDM Full Intent": m.get('fsdm_intent')
                        })
        
            if all_db_data:
                final_df = pd.DataFrame(all_db_data)
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='Semantic Mappings')
            
                st.download_button(
                    label="Download Final Mappings (Excel) 📥",
                    data=buffer.getvalue(),
                    file_name="semantic_mapping_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch',
                    type="primary"
                )
            else:
                st.warning("No completed mappings found to export.")

elif state.processing_mode == "Table":
    st.write("### 📊 Table-Level Mappings")
    
    table_results = ProjectManager.get_all_batch_mappings(state.current_project)

    if table_results:
        for res in table_results:
            table_id = res['table_id']
            with st.container(border=True):
                # Header: Table + Type + SQL
                col_l, col_r = st.columns([1, 4])
                with col_l:
                    st.markdown(f"**Table:** `{res['target_table']}`")
                    st.caption(f"ID: `{table_id}`")
                    st.caption(f"`{res['transformation_type']}`")
                    st.info(f"{res['mapping_status']}")

                with col_r:
                    st.code(res['transformation_logic'], language="sql")
                
                # Details Expander
                with st.expander("Details & Reasoning", expanded=False):
                    st.markdown("#### ⚙️ Batch SQL Engineering")
                    st.markdown(f"**Mapping Reasoning:**\n{res.get('reasoning', 'N/A')}")
    else:
        st.info("No table-level transformations generated yet.")
st.divider()

# Section 4: Logs
st.header("4. Application Logs 📑"  )
display_logs(state, height=400, key_prefix="main_logs")

# # --- Mapping Execution Loop (State Machine) ---
if state.mapping_active:
    if state.processing_mode == "Row":
        # Track progress index
        if "mapping_idx" not in st.session_state:
            st.session_state["mapping_idx"] = 0
        
        selected_ids = state.selected_mapping_rows
        total_rows = len(selected_ids)

        if total_rows == 0:
            st.warning("No rows selected.")
            state.mapping_active = False
            st.rerun()

        if st.session_state["mapping_idx"] < total_rows:
            unique_id = selected_ids[st.session_state["mapping_idx"]]
            
            # Display progress
            st.progress((st.session_state["mapping_idx"]) / total_rows)
            st.info(f"Processing ({st.session_state['mapping_idx'] + 1}/{total_rows}): {unique_id}")
            
            # Fetch actual row data from unified_mapping_view
            unified_df = ProjectManager.load_df_from_sql(state.current_project, "unified_mapping_view")
            if not unified_df.empty:
                try:
                    parts = unique_id.split("|")
                    if len(parts) == 3:
                        f_name, s_name, r_idx_str = parts
                        r_idx = int(r_idx_str)
                        
                        row_data_raw = unified_df.loc[r_idx]
                        
                        target_table = row_data_raw.get('target_table', 'unknown_table')
                        target_col = row_data_raw.get('target_column', 'unknown_col')
                        source_table = row_data_raw.get('source_table', 'unknown_table')
                        source_col = row_data_raw.get('source_column', 'unknown_col')
                        
                        row_data = {
                            "source_info": {
                                "subject_area": row_data_raw.get("source_subject"),
                                "db_name": row_data_raw.get("source_db"),
                                "table_name": source_table,
                                "column_name": source_col,
                                "datatype": row_data_raw.get("source_type")
                            },
                            "target_info": {
                                "subject_area": row_data_raw.get("target_subject"),
                                "db_name": row_data_raw.get("target_db"),
                                "table_name": target_table,
                                "column_name": target_col,
                                "datatype": row_data_raw.get("target_type")
                            },
                            "physical_source_info": {
                                "subject_area": row_data_raw.get("physical_source_subject"),
                                "db_name": row_data_raw.get("physical_source_db"),
                                "table_name": row_data_raw.get("physical_source_table"),
                                "column_name": row_data_raw.get("physical_source_column"),
                                "datatype": row_data_raw.get("physical_source_type")
                            },
                            "transformation_specs": {
                                "type": row_data_raw.get("trans_type"),
                                "condition": row_data_raw.get("trans_condition"),
                                "remarks": row_data_raw.get("remarks")
                            },
                            "target_table": target_table
                        }
                        
                        executor = AgentExecutor(state)
                        res = executor.process_mapping_custom(row_data, r_idx)
                        ProjectManager.save_mapping_row(state.current_project, res)
                        st.write(f"✅ Saved result for {unique_id}")
                    else:
                        st.error(f"Invalid unique_id format: {unique_id}")
                except Exception as e:
                    st.error(f"Error processing row {unique_id}: {e}")
            
            st.session_state["mapping_idx"] += 1
            st.rerun()
        else:
            # Completion
            st.success("Row mapping complete!")
            state.mapping_active = False
            st.session_state["mapping_idx"] = 0
            state.save_project()
            st.rerun()

    elif state.processing_mode == "Table":
        # Table Batch Processing Logic
        with st.spinner("Processing selected tables..."):
            unified_df = ProjectManager.load_df_from_sql(state.current_project, "unified_mapping_view")
            
            for table_name in state.filter_tables:
                table_df = unified_df[unified_df['target_table'] == table_name]
                
                # Convert aggregated table data into a list of row dicts
                table_data = table_df.to_dict('records')
                
                # Mock result for now (Agent call pending)
                result = {
                    'target_table': table_name,
                    'mapping_status': 'Completed',
                    'transformation_type': 'Batch',
                    'transformation_logic': '-- Placeholder logic for table ' + table_name,
                    'reasoning': 'Generated via batch table processor.'
                }
                
                ProjectManager.save_batch_table_mapping(state.current_project, table_name, result)
            
            st.success("Table batch processing complete!")
            state.mapping_active = False
            state.save_project()
            st.rerun()

