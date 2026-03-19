import streamlit as st
import pandas as pd
import io
from logic import (
    process_pdf, 
    get_excel_sheets, 
    process_excel_sheets, 
    split_documents, 
    excel_col_to_idx,
    AppState,
    ProjectManager
)
from logic.utils import get_cell_value
from agent import create_agent
from ui import sidebar_config, display_logs

st.set_page_config(page_title="Semantic Mapper AI", layout="wide")

# Initialize State
state = AppState()

# --- Project Selection ---
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
            if col_open.button("Open Project", type="primary", use_container_width=True):
                state.load_project(selected_proj)
                st.rerun()
                
            if col_del.button("Delete Project", type="secondary", use_container_width=True):
                 ProjectManager.delete_project(selected_proj)
                 st.success(f"Deleted project: {selected_proj}")
                 st.rerun()
        else:
            st.info("No projects found.")
            
    st.stop() 

# --- Main App ---

# Project Sidebar
with st.sidebar:
    st.markdown(f"### 📂 Project: {state.current_project}")
    if st.button("↩️ Switch Project", use_container_width=True):
        state.current_project = None
        state.reset_kb()
        st.rerun()
    st.divider()

sidebar_config(state)
st.title("Semantic Mapper AI 🧠")

# Section 1: Knowledge Base Manager
st.header("1. Knowledge Base Manager")

# --- 1. Upload Section ---
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

# --- 2. Dashboard Section ---
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
        if col_btn1.button("🔄 Sync with Vector Store", type="primary", use_container_width=True):
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
    
    if col_btn2.button("🧹 Clear All", use_container_width=True):
        state.reset_kb()
        state.save_project()
        st.rerun()

st.divider()

# Section 2: Mapping Configuration
st.header("2. Configure Mapping Document")

mapping_file = st.file_uploader("Upload Mapping Excel", type=["xlsx"], key="map_uploader")

# Process new upload
if mapping_file:
    file_bytes = mapping_file.read()
    sheets = get_excel_sheets(file_bytes)
    selected_map_sheet = st.selectbox("Select Mapping Sheet", sheets, key="map_sheet_selector")
    state.mapping_df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_map_sheet)
    state.save_project()

# Even if mapping_file is None (on rerun), we might have mapping_df from previous upload
if state.mapping_df is not None:
    df = state.mapping_df
    st.write("### Raw Data Preview")
    st.dataframe(df.head(), use_container_width=True)

    st.divider()
    st.subheader("Map Columns")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Target Fields")
        t_subj = st.text_input("Target Subject Area", placeholder="e.g. F", key="map_t_subj")
        t_db = st.text_input("Target DB Name", placeholder="e.g. G", key="map_t_db")
        t_tbl = st.text_input("Target Table Name", placeholder="e.g. H", key="map_t_tbl")
        t_col = st.text_input("Target Column Name", placeholder="e.g. I", key="map_t_col")
        t_type = st.text_input("Target Datatype", placeholder="e.g. J", key="map_t_type")

    with col2:
        st.markdown("### Source Fields")
        s_subj = st.text_input("Subject Area Column", placeholder="e.g. A", key="map_s_subj")
        s_db = st.text_input("DB Name Column", placeholder="e.g. B", key="map_s_db")
        s_tbl = st.text_input("Table Name Column", placeholder="e.g. C", key="map_s_tbl")
        s_col = st.text_input("Column Name Column", placeholder="e.g. D", key="map_s_col")
        s_type = st.text_input("Datatype Column", placeholder="e.g. E", key="map_s_type")
    
    st.subheader("Transformation Specs")
    c_tr1, c_tr2 = st.columns(2)
    tr_type = c_tr1.text_input("Transf. Type Column", placeholder="e.g. K", key="map_trans_type")
    tr_cond = c_tr2.text_input("Transf. Condition Column", placeholder="e.g. L", key="map_trans_cond")

    st.subheader("Row Range")
    c_r1, c_r2 = st.columns(2)
    r_start = c_r1.number_input("Start Row", min_value=1, max_value=len(df), key="map_r_start")
    r_end = c_r2.number_input("End Row", min_value=1, max_value=len(df), key="map_r_end")

    if st.button("Preview Mapping", use_container_width=True):
        st.session_state.show_mapping_preview = True
        state.save_project()
else:
    st.info("Please upload a mapping Excel file to begin.")
    # Default variables to avoid NameErrors
    s_subj = s_db = s_tbl = s_col = s_type = ""
    t_subj = t_db = t_tbl = t_col = t_type = ""
    tr_type = tr_cond = ""
    r_start = 1
    r_end = 1


if st.session_state.get("show_mapping_preview") and state.mapping_df is not None:
    st.divider()
    st.header("🔍 Resolved Mapping Preview")
    st.info(f"Showing resolved values for rows {r_start} to {r_end} based on your mapping configuration.")
    
    # Sync config
    state.mapping_config = {
        "source": {"subj": s_subj, "db": s_db, "tbl": s_tbl, "col": s_col, "type": s_type},
        "target": {"subj": t_subj, "db": t_db, "tbl": t_tbl, "col": t_col, "type": t_type},
        "transformation": {"type": tr_type, "cond": tr_cond},
        "range": (r_start, r_end)
    }
    
    # Resolve column indices from identifiers
    selected_indices = []
    for ident in [s_subj, s_db, s_tbl, s_col, s_type, t_subj, t_db, t_tbl, t_col, t_type, tr_type, tr_cond]:
        if not ident: continue
        if ident in state.mapping_df.columns:
            selected_indices.append(state.mapping_df.columns.get_loc(ident))
        else:
            idx = excel_col_to_idx(ident)
            if idx is not None and 0 <= idx < len(state.mapping_df.columns):
                selected_indices.append(idx)
    
    # Get unique columns in original order
    unique_indices = sorted(list(set(selected_indices)))
    
    if unique_indices:
        preview_df = state.mapping_df.iloc[r_start-1:r_end, unique_indices]
        st.dataframe(preview_df, use_container_width=True)
    else:
        st.warning("No valid columns mapped yet.")
    
    if st.button("🚀 Generate Mappings", type="primary", use_container_width=True, on_click=state.sync):
        
        # --- Inline Mapping Logic ---
        state.clear_logs()
        
        # 1. Initialize Agent
        llm_config = state.get_llm_config()
        state.add_log(f"Initializing agent with model: {llm_config['model_name']}")
        
        retriever = state.v_manager.get_retriever()
        
        def _log(message: str):
            state.add_log(message)
            
        agent = create_agent(
            retriever,
            model_name=llm_config["model_name"],
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
            log_callback=_log
        )
        
        # 2. Run Loop
        df = state.mapping_df
        conf = state.mapping_config
        results = []
        
        progress_bar = st.progress(0)
        total_rows = r_end - r_start + 1
        
        for i, idx in enumerate(range(r_start - 1, r_end)):
            if idx >= len(df): break
            
            row = df.iloc[idx]
            
            # Extract Data using helper
            source_info = {
                "subject_area": get_cell_value(row, s_subj),
                "db_name": get_cell_value(row, s_db),
                "table_name": get_cell_value(row, s_tbl),
                "column_name": get_cell_value(row, s_col),
                "datatype": get_cell_value(row, s_type)
            }
            target_info = {
                "subject_area": get_cell_value(row, t_subj),
                "db_name": get_cell_value(row, t_db),
                "table_name": get_cell_value(row, t_tbl),
                "column_name": get_cell_value(row, t_col),
                "datatype": get_cell_value(row, t_type)
            }
            
            transformation_specs = {
                "type": get_cell_value(row, tr_type),
                "condition": get_cell_value(row, tr_cond)
            }
            
            state.add_log(f"Processing Row {idx+1}: {source_info['column_name']} -> {target_info['column_name']}")
            
            try:
                res = agent.invoke({
                    "source_info": source_info,
                    "target_info": target_info,
                    "transformation_specs": transformation_specs,
                    "context": "",
                    "transformation_type": "",
                    "transformation_logic": "",
                    "reasoning": ""
                })
                
                result_entry = {
                    "row_idx": idx + 1,
                    "source_info": source_info,
                    "target_info": target_info,
                    **res
                }
                results.append(result_entry)
                state.add_log(f"✅ Success Row {idx+1}: {res['transformation_type']}")
                
            except Exception as e:
                state.add_log(f"❌ Error Row {idx+1}: {str(e)}")
                results.append({
                    "row_idx": idx + 1,
                    "source_info": source_info,
                    "target_info": target_info,
                    "transformation_type": "ERROR",
                    "transformation_logic": str(e),
                    "reasoning": "Processing failed."
                })
            
            progress_bar.progress((i + 1) / total_rows)
        
        state.results = results
        state.save_project() # Save results
        st.rerun()

st.divider()

# Section 3: Results
st.header("3. Transformation Results")

if not state.results:
    st.info("No results generated yet. Complete Step 2 above.")
else:
    # Action Bar
    col_act1, col_act2 = st.columns([4, 1])
    with col_act2:
        if st.button("🔄 Clear Results", use_container_width=True):
            state.results = []
            state.save_project()
            st.rerun()
    
    # Header for the results "table"
    h_cols = st.columns([0.5, 2, 2, 1.5, 2, 2, 2])
    h_cols[0].markdown("**Row**")
    h_cols[1].markdown("**Source Info**")
    h_cols[2].markdown("**Target Info**")
    h_cols[3].markdown("**Transf. Type**")
    h_cols[4].markdown("**Transf. Logic**")
    h_cols[5].markdown("**Reasoning**")
    h_cols[6].markdown("**Action & Feedback**")
    st.divider()

    for res in state.results:
        row_idx = res['row_idx']
        with st.container(border=True):
            c = st.columns([0.5, 2, 2, 1.5, 2, 2, 2])
            
            # Row Index
            c[0].write(f"#{row_idx}")
            
            # Source Info
            s = res['source_info']
            c[1].markdown(f"**Subj:** {s['subject_area']}\n\n**DB:** {s['db_name']}\n\n**Tbl:** {s['table_name']}\n\n**Col:** {s['column_name']}\n\n**Type:** {s['datatype']}")
            
            # Target Info
            t = res['target_info']
            c[2].markdown(f"**Subj:** {t['subject_area']}\n\n**DB:** {t['db_name']}\n\n**Tbl:** {t['table_name']}\n\n**Col:** {t['column_name']}\n\n**Type:** {t['datatype']}")
            
            # Transformation Type
            c[3].info(res['transformation_type'])
            
            # Transformation Logic
            c[4].code(res['transformation_logic'], language="sql")
            
            # Reasoning
            c[5].write(res['reasoning'])
            
            # Action & Feedback
            with c[6]:
                feedback = st.text_area("Feedback", value=st.session_state.get(f"feed_{row_idx}", ""), key=f"feed_{row_idx}", height=150)
                
                def on_regen_row(idx, feed):
                    state.sync()
                    with st.spinner(f"Regenerating row {idx}..."):
                        # Inline regeneration logic
                        # 1. Initialize Agent
                        llm_config = state.get_llm_config()
                        state.add_log(f"Initializing agent for regeneration with model: {llm_config['model_name']}")
                        retriever = state.v_manager.get_retriever()
                        def _log(message: str): state.add_log(message)
                        agent = create_agent(retriever, model_name=llm_config["model_name"], api_key=llm_config["api_key"], base_url=llm_config["base_url"], log_callback=_log)
                        
                        # 2. Find row
                        current_results = state.results
                        found_idx = -1
                        for i, r in enumerate(current_results):
                            if r["row_idx"] == idx:
                                found_idx = i
                                break
                        
                        if found_idx == -1:
                            state.add_log(f"⚠️ Cannot find Row {idx} in results for regeneration.")
                            return

                        row_data = current_results[found_idx]
                        state.add_log(f"Regenerating Row {idx} with feedback: {feed}")
                        
                        try:
                            new_res = agent.invoke({
                                "source_info": row_data["source_info"],
                                "target_info": row_data["target_info"],
                                "context": "",
                                "transformation_type": "",
                                "transformation_logic": "",
                                "reasoning": "",
                                "feedback": feed
                            })
                            
                            # Update the entry in state
                            current_results[found_idx].update(new_res)
                            state.results = current_results # Trigger state update
                            state.add_log(f"✅ Row {idx} regenerated successfully.")
                            state.save_project() # Save results
                        except Exception as e:
                            state.add_log(f"❌ Error regenerating Row {idx}: {str(e)}")

                st.button("🔄 Regenerate", key=f"btn_{row_idx}", on_click=on_regen_row, args=(row_idx, feedback), use_container_width=True, type="primary")

    # Export
    export_data = []
    for res in state.results:
        s = res['source_info']
        t = res['target_info']
        export_data.append({
            "Row": res['row_idx'],
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
            "Transformation Type": res['transformation_type'],
            "Transformation Logic": res['transformation_logic'],
            "Reasoning": res['reasoning']
        })
        
    final_df = pd.DataFrame(export_data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        final_df.to_excel(writer, index=False, sheet_name='Semantic Mappings')
    
    st.download_button(
        label="Download Final Mappings (Excel) 📥",
        data=buffer.getvalue(),
        file_name="semantic_mapping_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary"
    )

st.divider()

# Section 4: Logs
st.header("4. Application Logs 📑")
display_logs(state, height=400, key_prefix="main_logs")

# Final state sync to capture widget changes from this run
state.sync()
