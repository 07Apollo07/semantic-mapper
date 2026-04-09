import streamlit as st
import pandas as pd
import io
from logic import (
    process_pdf, 
    get_excel_sheets, 
    process_excel_sheets, 
    excel_to_sqlite,
    split_documents, 
    excel_col_to_idx,
    AppState,
    ProjectManager
)
from logic.utils import get_cell_value
from agent import create_agent, AgentExecutor
from ui import sidebar_config, display_logs

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
st.header("1. Knowledge Base Manager")

#  --- 1. Upload Section ---
uploaded_files = st.file_uploader("Upload PDFs or Excel Sheets", accept_multiple_files=True, type=["pdf", "xlsx"], key="uploader")

if uploaded_files:
    inventory = state.kb_inventory
    for f in uploaded_files:
        if not any(item["name"] == f.name for item in inventory):
            f.seek(0)
            file_bytes = f.read()
            
            # Save to disk
            ProjectManager.save_file(state.current_project, f.name, file_bytes)
            
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
                    "sheets": {s: {"selected": True, "indexed": False} for s in sheets}
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
                indexed_count = sum(1 for s in sheets_data.values() if s["indexed"])
                selected_count = sum(1 for s in sheets_data.values() if s["selected"])
                
                if indexed_count == selected_count and indexed_count > 0:
                    col_status.success(f"✅ {indexed_count} Sheets")
                elif indexed_count > 0:
                    col_status.warning(f"🟠 {indexed_count}/{selected_count} Sync")
                    needs_sync = True
                elif selected_count > 0:
                    col_status.info(f"⏳ {selected_count} Pending")
                    needs_sync = True
                
                if any(s["selected"] != s["indexed"] for s in sheets_data.values()):
                    needs_sync = True

                col_name.markdown(f"📊 **{item['name']}**")
                with col_name.expander("Show Sheets"):
                    for s_name, s_info in sheets_data.items():
                        s_col1, s_col2 = st.columns([3, 1])
                        checked = s_col1.checkbox(f"{s_name}", value=s_info["selected"], key=f"sel_{item['name']}_{s_name}")
                        if checked != s_info["selected"]:
                            inventory[idx]["sheets"][s_name]["selected"] = checked
                            state.kb_inventory = inventory
                            state.save_project()
                            st.rerun()
                        if s_info["indexed"]:
                            s_col2.markdown(":green[Indexed]")
            
            if col_rm.button("🗑️", key=f"del_file_{idx}"):
                # Remove from vector store
                if item["type"] == "pdf" and item["indexed"]:
                    state.v_manager.remove_document(item["name"])
                elif item["type"] == "excel":
                    for s_name, s_info in item["sheets"].items():
                        if s_info["indexed"]:
                            state.v_manager.remove_document(item["name"], s_name)
                
                # Remove from disk
                ProjectManager.delete_file(state.current_project, item["name"])
                
                inventory.pop(idx)
                state.kb_inventory = inventory
                state.save_project()
                st.rerun()
        st.divider()

    # --- 3. Action Buttons ---
    col_btn1, col_btn2 = st.columns([1, 1])
    if needs_sync:
        if col_btn1.button("🔄 Sync with Vector Store", type="primary", width='stretch'):
            with st.spinner("Syncing changes..."):
                for idx, item in enumerate(inventory):
                    if item["type"] == "pdf":
                        if item["selected"] and not item["indexed"]:
                            chunks = split_documents(process_pdf(item["bytes"], item["name"]))
                            state.v_manager.add_documents(chunks)
                            inventory[idx]["indexed"] = True
                        elif not item["selected"] and item["indexed"]:
                            state.v_manager.remove_document(item["name"])
                            inventory[idx]["indexed"] = False
                    else: # Excel
                        for s_name, s_info in item["sheets"].items():
                            if s_info["selected"] and not s_info["indexed"]:
                                chunks = split_documents(process_excel_sheets(item["bytes"], item["name"], [s_name]))
                                state.v_manager.add_documents(chunks)
                                inventory[idx]["sheets"][s_name]["indexed"] = True
                            elif not s_info["selected"] and s_info["indexed"]:
                                state.v_manager.remove_document(item["name"], s_name)
                                inventory[idx]["sheets"][s_name]["indexed"] = False
                state.kb_inventory = inventory
                state.save_project()
                st.success("Vector Store synced!")
                st.rerun()
    
    if col_btn2.button("🧹 Clear All", width='stretch'):
        state.reset_kb()
        state.save_project()
        st.rerun()

st.divider()

#  Section 1.2: Knowledge Base DB Manager
st.header("1.2 Knowledge Base DB Manager")

#  --- 1. Upload Section ---
fsdm_uploaded_files = st.file_uploader("Upload FSDM/ETL Excel Sheets", accept_multiple_files=True, type=["xlsx"], key="fsdm_uploader")

if fsdm_uploaded_files:
    fsdm_inventory = state.fsdm_inventory
    for f in fsdm_uploaded_files:
        if not any(item["name"] == f.name for item in fsdm_inventory):
            f.seek(0)
            file_bytes = f.read()
            
            # Save to disk
            ProjectManager.save_file(state.current_project, f.name, file_bytes)
            
            sheets = get_excel_sheets(file_bytes)
            fsdm_inventory.append({
                "name": f.name,
                "type": "excel",
                "bytes": file_bytes,
                "sheets": {s: {"selected": True, "indexed": False} for s in sheets}
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
            indexed_count = sum(1 for s in sheets_data.values() if s["indexed"])
            selected_count = sum(1 for s in sheets_data.values() if s["selected"])
            
            if indexed_count == selected_count and indexed_count > 0:
                col_status.success(f"✅ {indexed_count} Tables")
            elif indexed_count > 0:
                col_status.warning(f"🟠 {indexed_count}/{selected_count} Sync")
                needs_db_sync = True
            elif selected_count > 0:
                col_status.info(f"⏳ {selected_count} Pending")
                needs_db_sync = True
            
            if any(s["selected"] != s["indexed"] for s in sheets_data.values()):
                needs_db_sync = True

            col_name.markdown(f"📊 **{item['name']}**")
            with col_name.expander("Show Sheets"):
                for s_name, s_info in sheets_data.items():
                    s_col1, s_col2 = st.columns([3, 1])
                    checked = s_col1.checkbox(f"{s_name}", value=s_info["selected"], key=f"sel_fsdm_{item['name']}_{s_name}")
                    if checked != s_info["selected"]:
                        fsdm_inventory[idx]["sheets"][s_name]["selected"] = checked
                        state.fsdm_inventory = fsdm_inventory
                        state.save_project()
                        st.rerun()
                    if s_info["indexed"]:
                        s_col2.markdown(":green[In DB]")
            
            if col_rm.button("🗑️", key=f"del_fsdm_file_{idx}"):
                # --- NEW LOGIC START ---
                # Drop associated tables from DB before deleting the file
                ProjectManager.drop_excel_sheets_from_db(state.current_project, item["name"], item["sheets"])
                # --- NEW LOGIC END ---

                # Remove from disk
                ProjectManager.delete_file(state.current_project, item["name"])
                
                fsdm_inventory.pop(idx)
                state.fsdm_inventory = fsdm_inventory
                state.save_project()
                st.rerun()
        st.divider()

    # --- 3. Action Buttons ---
    if needs_db_sync:
        if st.button("🗄️ Create DB / Sync Tables", type="primary", width='stretch'):
            with st.spinner("Syncing to SQLite..."):
                for idx, item in enumerate(fsdm_inventory):
                    selected_sheets = [s for s, info in item["sheets"].items() if info["selected"] and not info["indexed"]]
                    if selected_sheets:
                        excel_to_sqlite(item["bytes"], state.current_project, selected_sheets)
                        for s in selected_sheets:
                            fsdm_inventory[idx]["sheets"][s]["indexed"] = True
                
                state.fsdm_inventory = fsdm_inventory
                state.save_project()
                st.success("SQLite DB updated!")
                st.rerun()

st.divider()

#  Section 2: Mapping Configuration
st.header("2. Configure Mapping Document")

mapping_file = st.file_uploader("Upload Mapping Excel", type=["xlsx"], key="map_uploader")

#  Process new upload
if mapping_file:
    file_bytes = mapping_file.read()
    sheets = get_excel_sheets(file_bytes)
    selected_map_sheet = st.selectbox("Select Mapping Sheet", sheets, key="map_sheet_selector")
    state.mapping_df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_map_sheet)
    # Ingest into SQLite
    # ProjectManager.save_df_to_sql(state.current_project, "mapping_sheet", state.mapping_df)
    state.save_project()

#  Even if mapping_file is None (on rerun), we might have mapping_df from previous upload
if state.mapping_df is not None:
    df = state.mapping_df
    st.write("### Raw Data Preview")
    st.dataframe(df.head(), width='stretch')

    st.divider()
    st.subheader("Map Columns")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Target Fields")
        t_subj = st.text_input("Target Subject Area", value=state.map_t_subj, placeholder="e.g. F", key="map_t_subj")
        t_db = st.text_input("Target DB Name", value=state.map_t_db, placeholder="e.g. G", key="map_t_db")
        t_tbl = st.text_input("Target Table Name", value=state.map_t_tbl, placeholder="e.g. H", key="map_t_tbl")
        t_col = st.text_input("Target Column Name", value=state.map_t_col, placeholder="e.g. I", key="map_t_col")
        t_type = st.text_input("Target Datatype", value=state.map_t_type, placeholder="e.g. J", key="map_t_type")

    with col2:
        st.markdown("### Source Fields")
        s_subj = st.text_input("Subject Area Column", value=state.map_s_subj, placeholder="e.g. A", key="map_s_subj")
        s_db = st.text_input("DB Name Column", value=state.map_s_db, placeholder="e.g. B", key="map_s_db")
        s_tbl = st.text_input("Table Name Column", value=state.map_s_tbl, placeholder="e.g. C", key="map_s_tbl")
        s_col = st.text_input("Column Name Column", value=state.map_s_col, placeholder="e.g. D", key="map_s_col")
        s_type = st.text_input("Datatype Column", value=state.map_s_type, placeholder="e.g. E", key="map_s_type")
    
    st.subheader("Transformation Specs")
    c_tr1, c_tr2, c_tr3 = st.columns(3)
    tr_type = c_tr1.text_input("Transf. Type Column", value=state.map_trans_type, placeholder="e.g. K", key="map_trans_type")
    tr_cond = c_tr2.text_input("Transf. Condition Column", value=state.map_trans_cond, placeholder="e.g. L", key="map_trans_cond")
    tr_remarks = c_tr3.text_input("Remarks Column", value=state.map_remarks, placeholder="e.g. M", key="map_remarks")

    # --- Column Configuration Identifiers ---
    mapping_config_identifiers = [
        s_subj, s_db, s_tbl, s_col, s_type,
        t_subj, t_db, t_tbl, t_col, t_type,
        tr_type, tr_cond, tr_remarks
    ]

    # --- Column-config change detection: rebuild mapping_sheet ---
    _col_sig = "|".join([str(i) for i in mapping_config_identifiers])
    if st.session_state.get("col_config_sig") != _col_sig:
        if st.session_state.get("col_config_sig") is not None and state.current_project and state.mapping_df is not None:
            # Config changed — drop and rebuild the mapping_sheet table
            ProjectManager.rebuild_mapping_from_config(state.current_project, state.mapping_df, mapping_config_identifiers)
            st.session_state.show_mapping_preview = False
        st.session_state["col_config_sig"] = _col_sig

    st.divider()
    st.subheader("Project-Wide Instructions 🌐")
    state.global_instructions = st.text_area("Global Instructions (e.g., standard null handling, date formats)", value=state.global_instructions, height=100)

    st.divider()
    st.subheader("Select Execution Target 🎯")
    
    # Extract unique target tables from the mapping DF
    target_tables = []
    if t_tbl:
        if t_tbl in state.mapping_df.columns:
            target_tables = state.mapping_df[t_tbl].dropna().unique().tolist()
        else:
            idx = excel_col_to_idx(t_tbl)
            if idx is not None and 0 <= idx < len(state.mapping_df.columns):
                target_tables = state.mapping_df.iloc[:, idx].dropna().unique().tolist()
    
    target_tables = sorted(list(set([str(t).strip() for t in target_tables])))
    state.selected_target_table = st.selectbox("Target Table to Process", options=target_tables, index=0 if state.selected_target_table in target_tables else 0 if target_tables else None)

    if st.button("🔍 Preview & Prepare Table", width='stretch'):
        # Rebuild based on latest config
        ProjectManager.rebuild_mapping_from_config(state.current_project, state.mapping_df, mapping_config_identifiers)
        
        st.session_state.show_mapping_preview = True
        state.save_project()
        st.rerun()
else:
    st.info("Please upload a mapping Excel file to begin.")
    # Default variables to avoid NameErrors
    s_subj = s_db = s_tbl = s_col = s_type = ""
    t_subj = t_db = t_tbl = t_col = t_type = ""
    tr_type = tr_cond = tr_remarks = ""


if st.session_state.get("show_mapping_preview") and state.mapping_df is not None:
    st.divider()
    st.header(f"🔍 Table Scope: {state.selected_target_table}")
    
    # Load the column-filtered mapping data from the DB for preview
    preview_base_df = ProjectManager.load_df_from_sql(state.current_project, "mapping_sheet")
    # Ensure it's a DataFrame if empty or failed to load
    if not isinstance(preview_base_df, pd.DataFrame):
        preview_base_df = pd.DataFrame()

    # Filter loaded DataFrame by selected target table
    t_tbl_col = state.map_t_tbl
    if t_tbl_col in preview_base_df.columns: # Check column existence in preview_base_df
        filtered_df = preview_base_df[preview_base_df[t_tbl_col].astype(str).str.strip() == state.selected_target_table]
    else:
        idx = excel_col_to_idx(t_tbl_col)
        # Check if idx is valid and preview_base_df has enough columns
        if idx is not None and 0 <= idx < len(preview_base_df.columns):
            filtered_df = preview_base_df[preview_base_df.iloc[:, idx].astype(str).str.strip() == state.selected_target_table]
        else:
            filtered_df = pd.DataFrame() # Handle cases where column is not found or df is too narrow

    st.info(f"Found {len(filtered_df)} rows for target table `{state.selected_target_table}`.")
    with st.expander("View Filtered Rows"):
        st.dataframe(filtered_df, width='stretch')
    
    # Sync config
    state.mapping_config = {
        "source": {"subj": s_subj, "db": s_db, "tbl": s_tbl, "col": s_col, "type": s_type},
        "target": {"subj": t_subj, "db": t_db, "tbl": t_tbl, "col": t_col, "type": t_type},
        "transformation": {"type": tr_type, "cond": tr_cond, "remarks": tr_remarks}
    }
    
    # Pre-mapping Insight Phase
    st.subheader("Step 2.5: Pre-mapping Insights 🧠")
    st.markdown("Verify the 'Technical Intent' for each row before generating SQL.")
    
    executor = AgentExecutor(state)
    
    # Load existing mappings from DB
    existing_mappings = {m['row_idx']: m for m in ProjectManager.get_mappings_by_table(state.current_project, state.selected_target_table)}
    
    rows_to_process = []
    for idx, row in filtered_df.iterrows():
        row_idx = idx + 1
        row_info = executor.extract_row_info(row, state.mapping_config)
        row_info['row_idx'] = row_idx
        row_info['target_table'] = state.selected_target_table
        
        # If not in DB, initialize it
        if row_idx not in existing_mappings:
            ProjectManager.save_mapping_row(state.current_project, row_info)
            existing_mappings[row_idx] = row_info
            
        rows_to_process.append(existing_mappings[row_idx])

    # --- Batch Intent Generation Controls ---
    unverified_intents = [m for m in rows_to_process if m.get('validation_status') == 'Pending']
    col_batch1, col_batch2 = st.columns(2)
    with col_batch1:
        batch_label = f"🤖 Generate Intent for All Rows ({len(unverified_intents)} unverified)"
        if st.button(batch_label, type="primary", use_container_width=True, disabled=len(unverified_intents) == 0 or state.preprocessing_active):
            state.preprocessing_active = True
            state.preprocessing_idx = 0
            state.save_project()
            st.rerun()
    with col_batch2:
        if st.button("🛑 Stop Intent Generation", type="secondary", use_container_width=True, disabled=not state.preprocessing_active):
            state.preprocessing_active = False
            state.preprocessing_idx = 0
            state.save_project()
            st.rerun()
    
    if state.preprocessing_active:
        total_rows = len(rows_to_process)
        completed_intents = len([m for m in rows_to_process if m.get('pre_mapping_insight')])
        st.progress(completed_intents / total_rows if total_rows > 0 else 0)
        st.info(f"Generating intents: {completed_intents}/{total_rows} completed...")
    
    st.divider()

    # Display Preprocessing UI
    for m in rows_to_process:
        row_idx = m['row_idx']
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            c1.markdown(f"**Row #{row_idx}**")
            
            # Status Indicator
            v_status = m.get('validation_status', 'Pending')
            if v_status == 'Pending':
                c1.caption("🟡 Pending Intent")
            elif v_status == 'Intent Verified':
                c1.caption("🟢 Intent Verified")
            elif v_status == 'Mapping Complete':
                c1.caption("🔵 Mapped")
            elif v_status == 'SQL Verified':
                c1.caption("🔒 SQL Verified")
                
            c1.caption(f"`{m['source_info']['column_name']}` → `{m['target_info']['column_name']}`")
            
            # Insight Area
            insight = m.get('pre_mapping_insight', '')
            if not insight:
                if c2.button("🧠 Generate Intent", key=f"gen_ins_{row_idx}"):
                    insight = executor.generate_insight(m)
                    ProjectManager.update_mapping_validation(state.current_project, row_idx, {"pre_mapping_insight": insight})
                    st.session_state[f"ins_val_{row_idx}"] = insight
                    st.rerun()
            
            if insight:
                # Use session state to store the value for the text area to allow programmatic updates
                if f"ins_val_{row_idx}" not in st.session_state:
                    st.session_state[f"ins_val_{row_idx}"] = insight

                # Move Toggle up to control disabling of other widgets
                current_status = m.get('validation_status', 'Pending')
                is_verified_init = (current_status in ['Intent Verified', 'Mapping Complete', 'SQL Verified'])
                
                col_v1, col_v2 = c2.columns([1, 1])
                is_verified = col_v1.toggle("Verify Intent", value=is_verified_init, key=f"v_tog_{row_idx}")
                
                # Update status if toggled
                if is_verified != is_verified_init:
                    new_status = "Intent Verified" if is_verified else "Pending"
                    ProjectManager.update_mapping_validation(state.current_project, row_idx, {"validation_status": new_status})
                    st.rerun()
                
                new_insight = c2.text_area("Technical Intent / Hypothesis", value=st.session_state[f"ins_val_{row_idx}"], key=f"ins_val_ta_{row_idx}", height=100, disabled=is_verified)
                if not is_verified and new_insight != st.session_state[f"ins_val_{row_idx}"]:
                    st.session_state[f"ins_val_{row_idx}"] = new_insight
                    ProjectManager.update_mapping_validation(state.current_project, row_idx, {"pre_mapping_insight": new_insight, "validation_status": "Pending"})
                
                # Feedback & Regeneration
                with c2.expander("Regenerate with Hints"):
                    hint = st.text_area("Hints/Feedback for intent", placeholder="e.g. Use JOIN instead of union, filter for active status...", key=f"hint_{row_idx}", disabled=is_verified)
                    
                    def regen_callback(ridx, rdata, h):
                        # This runs BEFORE the main script rendering
                        new_insight_gen = executor.generate_insight(rdata, feedback=h)
                        ProjectManager.update_mapping_validation(state.current_project, ridx, {"pre_mapping_insight": new_insight_gen, "validation_status": "Pending"})
                        st.session_state[f"ins_val_{ridx}"] = new_insight_gen
                        # This is now safe because the widget hasn't been instantiated in this run yet
                        st.session_state[f"ins_val_ta_{ridx}"] = new_insight_gen

                    st.button("🔄 Regenerate Intent", key=f"reg_ins_{row_idx}", on_click=regen_callback, args=(row_idx, m, hint), disabled=is_verified)

    # --- Mapping Execution Controls ---
    num_ready = len([m for m in rows_to_process if m.get('validation_status') == 'Intent Verified'])
    st.divider()
    col_gen, col_stop = st.columns(2)
    with col_gen:
        btn_label = f"🚀 Generate SQL Mappings ({num_ready} rows)" if num_ready > 0 else "🚀 Generate SQL Mappings"
        if st.button(btn_label, type="primary", use_container_width=True, disabled=num_ready == 0 or state.mapping_active):
            state.mapping_active = True
            state.mapping_idx = 0 # We'll iterate through rows_to_process
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

# Pull results from DB for current table
if state.selected_target_table:
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
            with st.expander("Details, Reasoning & Feedback"):
                st.markdown(f"**Intent:** {res.get('pre_mapping_insight')}")
                st.markdown(f"**Reasoning:** {res['reasoning']}")
                
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
                
                def on_regen_row(idx, feed, row_data):
                    state.sync()
                    with st.spinner(f"Regenerating..."):
                        executor = AgentExecutor(state)
                        new_res = executor.process_row(row_data, idx, feedback=feed)
                        # Save back to DB
                        ProjectManager.save_mapping_row(state.current_project, {**row_data, **new_res, "validation_status": "Mapping Complete"})
                
                if st.button("🔄 Regenerate SQL", key=f"btn_{row_idx}", on_click=on_regen_row, args=(row_idx, feedback, res), disabled=sql_is_verified):
                    st.rerun()

    # Export all tables from DB
    if st.button("📦 Export All Processed Tables to Excel", width='stretch'):
        all_db_data = []
        # We'll get all unique tables and export them
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
                        "Source Subject Area": s['subject_area'],
                        "Source DB Name": s['db_name'],
                        "Source Table Name": s['table_name'],
                        "Source Column Name": s['column_name'],
                        "Source Datatype": s['datatype'],
                        "Target Subject Area": t['subject_area'],
                        "Target DB Name": t['db_name'],
                        "Target Table Name": t['table_name'],
                        "Target Column Name": t['column_name'],
                        "Target Datatype": t['datatype'],
                        "Transformation Type": m['transformation_type'],
                        "Transformation Logic": m['transformation_logic'],
                        "Reasoning": m['reasoning']
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

st.divider()

# Section 4: Logs
st.header("4. Application Logs 📑"  )
display_logs(state, height=400, key_prefix="main_logs")

# --- Preprocessing Loop (Batch Intent Generation) ---
if state.preprocessing_active:
    # If already processing, show status and stop to avoid re-triggering
    if st.session_state.get("processing_intent", False):
        st.info("Generating intent...")
        st.stop()

    # Get ALL rows for the table
    db_rows = ProjectManager.get_mappings_by_table(state.current_project, state.selected_target_table)
    
    if state.preprocessing_idx < len(db_rows):
        m = db_rows[state.preprocessing_idx]
        
        # Only process if status is Pending (unverified)
        if m.get('validation_status') == 'Pending':
            st.session_state["processing_intent"] = True
            executor = AgentExecutor(state)
            row_idx = m['row_idx']
            
            # Generate insight
            insight = executor.generate_insight(m)
            ProjectManager.update_mapping_validation(state.current_project, row_idx, {"pre_mapping_insight": insight})
            st.session_state[f"ins_val_{row_idx}"] = insight
            st.session_state["processing_intent"] = False

        # Increment index and rerun
        state.preprocessing_idx += 1
        st.rerun()
    else:
        # Completion Check
        state.preprocessing_active = False
        state.preprocessing_idx = 0
        state.save_project()
        st.rerun()


# --- Mapping Execution Loop (State Machine) ---
if state.mapping_active:
    # Stop Button
    if st.button("🛑 Stop Mapping", type="secondary", use_container_width=True, key="stop_mapping_bottom"):
        state.mapping_active = False
        state.save_project()
        st.session_state["processing_row"] = False
        st.rerun()

    # If already processing, show status and stop to avoid re-triggering
    if st.session_state.get("processing_row", False):
        st.info("Mapping in progress...")
        st.stop()

    # Get rows that are intent-verified but not yet mapped
    db_rows = ProjectManager.get_mappings_by_table(state.current_project, state.selected_target_table)
    pending_rows = [r for r in db_rows if r.get('validation_status') == 'Intent Verified']
    
    if pending_rows:
        st.session_state["processing_row"] = True
        
        executor = AgentExecutor(state)
        # Process the first pending row
        m = pending_rows[0]
        row_idx = m['row_idx']
        
        # Progress bar
        total_in_table = len(db_rows)
        processed_count = len([r for r in db_rows if r.get('validation_status') in ['Mapping Complete', 'SQL Verified']])
        st.progress((processed_count + 1) / total_in_table)
        
        # Process row
        result = executor.process_row(m, row_idx)
        
        # Update state in DB
        ProjectManager.save_mapping_row(state.current_project, {**m, **result, "validation_status": "Mapping Complete"})
        
        # Reset flag
        st.session_state["processing_row"] = False
        st.rerun()
    else:
        # Completion Check
        state.mapping_active = False
        state.save_project()
        st.success("Table mapping complete!")
        st.rerun()

