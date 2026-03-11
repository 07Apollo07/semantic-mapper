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
    MappingEngine
)
from ui import sidebar_config, step_indicator, display_logs

st.set_page_config(page_title="Semantic Mapper AI", layout="wide")

# Initialize State
state = AppState()

sidebar_config()
st.title("Semantic Mapper AI 🧠")
step_indicator(state.step)

# Step 1: Knowledge Base Manager
if state.step == 1:
    st.header("Knowledge Base Manager")
    
    # --- 1. Upload Section ---
    uploaded_files = st.file_uploader("Upload PDFs or Excel Sheets", accept_multiple_files=True, type=["pdf", "xlsx"], key="uploader")
    
    if uploaded_files:
        inventory = state.kb_inventory
        for f in uploaded_files:
            if not any(item["name"] == f.name for item in inventory):
                f.seek(0)
                file_bytes = f.read()
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
                                st.rerun()
                            if s_info["indexed"]:
                                s_col2.markdown(":green[Indexed]")
                
                if col_rm.button("🗑️", key=f"del_file_{idx}"):
                    if item["type"] == "pdf" and item["indexed"]:
                        state.v_manager.remove_document(item["name"])
                    elif item["type"] == "excel":
                        for s_name, s_info in item["sheets"].items():
                            if s_info["indexed"]:
                                state.v_manager.remove_document(item["name"], s_name)
                    inventory.pop(idx)
                    state.kb_inventory = inventory
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
                    st.success("Vector Store synced!")
                    st.rerun()
        
        if col_btn2.button("🧹 Clear All", use_container_width=True):
            state.reset_kb()
            st.rerun()

        # Navigation
        has_indexed = any(
            (i["type"] == "pdf" and i["indexed"]) or 
            (i["type"] == "excel" and any(s["indexed"] for s in i["sheets"].values())) 
            for i in state.kb_inventory
        )
        if has_indexed:
            st.divider()
            
            def go_next_step2():
                state.sync()
                state.step = 2

            st.button("Next: Configure Mapping ➡️", type="primary", use_container_width=True, on_click=go_next_step2)

# Step 2: Mapping Configuration
elif state.step == 2:
    st.header("Configure Mapping Document")

    mapping_file = st.file_uploader("Upload Mapping Excel", type=["xlsx"], key="map_uploader")

    # Process new upload
    if mapping_file:
        file_bytes = mapping_file.read()
        sheets = get_excel_sheets(file_bytes)
        selected_map_sheet = st.selectbox("Select Mapping Sheet", sheets, key="map_sheet_selector")
        state.mapping_df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_map_sheet)
    
    # Even if mapping_file is None (on rerun), we might have mapping_df from previous upload
    if state.mapping_df is not None:
        df = state.mapping_df
        st.write("### Raw Data Preview")
        st.dataframe(df.head(), use_container_width=True)

        st.divider()
        st.subheader("Map Columns")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Source Fields")
            s_subj = st.text_input("Subject Area Column", value=st.session_state.map_s_subj, placeholder="e.g. A", key="map_s_subj")
            s_db = st.text_input("DB Name Column", value=st.session_state.map_s_db, placeholder="e.g. B", key="map_s_db")
            s_tbl = st.text_input("Table Name Column", value=st.session_state.map_s_tbl, placeholder="e.g. C", key="map_s_tbl")
            s_col = st.text_input("Column Name Column", value=st.session_state.map_s_col, placeholder="e.g. D", key="map_s_col")
            s_type = st.text_input("Datatype Column", value=st.session_state.map_s_type, placeholder="e.g. E", key="map_s_type")
        with col2:
            st.markdown("### Target Fields")
            t_subj = st.text_input("Target Subject Area", value=st.session_state.map_t_subj, placeholder="e.g. F", key="map_t_subj")
            t_db = st.text_input("Target DB Name", value=st.session_state.map_t_db, placeholder="e.g. G", key="map_t_db")
            t_tbl = st.text_input("Target Table Name", value=st.session_state.map_t_tbl, placeholder="e.g. H", key="map_t_tbl")
            t_col = st.text_input("Target Column Name", value=st.session_state.map_t_col, placeholder="e.g. I", key="map_t_col")
            t_type = st.text_input("Target Datatype", value=st.session_state.map_t_type, placeholder="e.g. J", key="map_t_type")

        st.subheader("Row Range")
        c_r1, c_r2 = st.columns(2)
        r_start = c_r1.number_input("Start Row", min_value=1, max_value=len(df), value=int(st.session_state.map_r_start), key="map_r_start")
        r_end = c_r2.number_input("End Row", min_value=1, max_value=len(df), value=int(st.session_state.map_r_end), key="map_r_end")

        c_nav1, c_nav2 = st.columns([1, 1])
        with c_nav1:
            def go_back_step1():
                state.sync()
                state.step = 1
            st.button("⬅️ Back to Step 1", on_click=go_back_step1, use_container_width=True)
            
        with c_nav2:
            if st.button("Preview Mapping", use_container_width=True):
                st.session_state.show_mapping_preview = True
    else:
        st.info("Please upload a mapping Excel file to begin.")
        # Default variables to avoid NameErrors
        s_subj = s_db = s_tbl = s_col = s_type = ""
        t_subj = t_db = t_tbl = t_col = t_type = ""
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
            "range": (r_start, r_end)
        }
        
        engine = MappingEngine(state)
        
        # Resolve column indices from identifiers
        selected_indices = []
        for ident in [s_subj, s_db, s_tbl, s_col, s_type, t_subj, t_db, t_tbl, t_col, t_type]:
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
        
        def on_generate_mappings():
            state.sync()
            # We can't run long blocking code in callback easily with progress bar updates in main thread
            # So we set a flag or just let the button return True naturally, BUT we must sync first.
            # However, for this specific heavy action, it's better to keep it in the main body 
            # but ensure we synced.
            pass

        if st.button("🚀 Generate Mappings", type="primary", use_container_width=True, on_click=state.sync):
            progress_bar = st.progress(0)
            
            engine.progress_callback = progress_bar.progress
            # We don't need a custom on_log here because display_logs will handle the full view
            
            state.clear_logs()
            engine.run(r_start, r_end)
            
            state.step = 3
            st.rerun()

    # Always show logs at the bottom of Step 2 if generation has started or there are logs
    if state.logs:
        st.divider()
        display_logs(state, height=300, key_prefix="step2")

# Step 3: Results
elif state.step == 3:
    st.header("Transformation Results")
    
    if not state.results:
        st.warning("⚠️ No results generated. Go back to Step 2.")
        
        def go_back_step2():
            state.sync()
            state.step = 2
            
        st.button("⬅️ Back to Step 2", on_click=go_back_step2)
    else:
        # Action Bar
        col_act1, col_act2 = st.columns([4, 1])
        with col_act2:
            def on_regenerate_all():
                state.sync()
                state.step = 2
                
            st.button("🔄 Regenerate All", use_container_width=True, on_click=on_regenerate_all)
        
        # Results Display
        engine = MappingEngine(state)
        
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
                            engine.regenerate_row(idx, feed)

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
        def go_to_logs():
            state.sync()
            state.step = 4
        st.button("View Full Generation Logs 📑", on_click=go_to_logs, use_container_width=True)

# Step 4: Logs
elif state.step == 4:
    st.header("Application Logs 📑")
    display_logs(state, height=600, key_prefix="step4")

# Final state sync to capture widget changes from this run
state.sync()
