import streamlit as st
import pandas as pd
import io
from logic import process_pdf, get_excel_sheets, process_excel_sheets, split_documents, VectorStoreManager, excel_col_to_idx
from agent import create_agent
from ui import sidebar_config, step_indicator

st.set_page_config(page_title="Semantic Mapper AI", layout="wide")

# Initialize Session State
if "step" not in st.session_state:
    st.session_state.step = 1
if "kb_inventory" not in st.session_state:
    st.session_state.kb_inventory = [] # List of dicts: {id, name, type, sheets (optional), status}
if "v_manager" not in st.session_state or not hasattr(st.session_state.v_manager, "add_documents"):
    st.session_state.v_manager = VectorStoreManager()
if "mapping_df" not in st.session_state:
    st.session_state.mapping_df = None
if "mapping_config" not in st.session_state:
    st.session_state.mapping_config = {}
if "mapping_inputs" not in st.session_state:
    st.session_state.mapping_inputs = {}
if "show_mapping_preview" not in st.session_state:
    st.session_state.show_mapping_preview = False
if "results" not in st.session_state:
    st.session_state.results = []

sidebar_config()
st.title("Semantic Mapper AI 🧠")
step_indicator(st.session_state.step)

# Step 1: Knowledge Base Manager
if st.session_state.step == 1:
    st.header("Knowledge Base Manager")
    
    # --- 1. Upload Section ---
    uploaded_files = st.file_uploader("Upload PDFs or Excel Sheets", accept_multiple_files=True, type=["pdf", "xlsx"], key="uploader")
    print(st.session_state.kb_inventory)
    if uploaded_files:
        for f in uploaded_files:
            # Check if already in inventory
            if not any(item["name"] == f.name for item in st.session_state.kb_inventory):
                f.seek(0)
                file_bytes = f.read()
                if f.name.endswith(".pdf"):
                    st.session_state.kb_inventory.append({
                        "name": f.name,
                        "type": "pdf",
                        "bytes": file_bytes,
                        "selected": True, # Target state
                        "indexed": False  # Current state
                    })
                elif f.name.endswith(".xlsx"):
                    sheets = get_excel_sheets(file_bytes)
                    st.session_state.kb_inventory.append({
                        "name": f.name,
                        "type": "excel",
                        "bytes": file_bytes,
                        "sheets": {s: {"selected": True, "indexed": False} for s in sheets}
                    })

    # --- 2. Dashboard Section ---
    if st.session_state.kb_inventory:
        st.subheader("Manage Documents")
        
        needs_sync = False
        
        for idx, item in enumerate(st.session_state.kb_inventory):
            with st.container():
                col_name, col_status, col_rm = st.columns([5, 2, 1])
                
                # Logic for status and selection
                if item["type"] == "pdf":
                    is_indexed = item["indexed"]
                    is_selected = item["selected"]
                    
                    if is_indexed and is_selected:
                        col_status.success("✅ Indexed")
                    elif not is_indexed and is_selected:
                        col_status.warning("⏳ Pending")
                        needs_sync = True
                    elif is_indexed and not is_selected:
                        col_status.info("🗑️ To Remove")
                        needs_sync = True
                    
                    # Selection toggle
                    new_sel = col_name.checkbox(f"📄 {item['name']}", value=is_selected, key=f"sel_pdf_{idx}")
                    if new_sel != is_selected:
                        st.session_state.kb_inventory[idx]["selected"] = new_sel
                        st.rerun()

                else: # Excel
                    sheets_data = item["sheets"]
                    indexed_count = sum(1 for s in sheets_data.values() if s["indexed"])
                    selected_count = sum(1 for s in sheets_data.values() if s["selected"])
                    total_sheets = len(sheets_data)
                    
                    # Overall status for Excel file
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

                    # File name and expander
                    col_name.markdown(f"📊 **{item['name']}**")
                    with col_name.expander("Show Sheets"):
                        for s_name, s_info in sheets_data.items():
                            s_col1, s_col2 = st.columns([3, 1])
                            
                            # Checkbox for sheet selection
                            checked = s_col1.checkbox(f"{s_name}", value=s_info["selected"], key=f"sel_{item['name']}_{s_name}")
                            if checked != s_info["selected"]:
                                st.session_state.kb_inventory[idx]["sheets"][s_name]["selected"] = checked
                                st.rerun()
                            
                            # Sheet-level status
                            if s_info["indexed"]:
                                s_col2.markdown(":green[Indexed]")
                
                # Remove from list (wipes from memory completely)
                if col_rm.button("🗑️", key=f"del_file_{idx}"):
                    # If it was indexed, we should remove from vector store first
                    if item["type"] == "pdf" and item["indexed"]:
                        st.session_state.v_manager.remove_document(item["name"])
                    elif item["type"] == "excel":
                        for s_name, s_info in item["sheets"].items():
                            if s_info["indexed"]:
                                st.session_state.v_manager.remove_document(item["name"], s_name)
                    
                    st.session_state.kb_inventory.pop(idx)
                    st.rerun()
            
            st.divider()

        # --- 3. Action Buttons ---
        col_btn1, col_btn2 = st.columns([1, 1])
        
        if needs_sync:
            if col_btn1.button("🔄 Sync with Vector Store", type="primary", use_container_width=True):
                with st.spinner("Syncing changes..."):
                    for idx, item in enumerate(st.session_state.kb_inventory):
                        if item["type"] == "pdf":
                            if item["selected"] and not item["indexed"]:
                                chunks = split_documents(process_pdf(item["bytes"], item["name"]))
                                st.session_state.v_manager.add_documents(chunks)
                                st.session_state.kb_inventory[idx]["indexed"] = True
                            elif not item["selected"] and item["indexed"]:
                                st.session_state.v_manager.remove_document(item["name"])
                                st.session_state.kb_inventory[idx]["indexed"] = False
                        
                        else: # Excel
                            for s_name, s_info in item["sheets"].items():
                                if s_info["selected"] and not s_info["indexed"]:
                                    chunks = split_documents(process_excel_sheets(item["bytes"], item["name"], [s_name]))
                                    st.session_state.v_manager.add_documents(chunks)
                                    st.session_state.kb_inventory[idx]["sheets"][s_name]["indexed"] = True
                                elif not s_info["selected"] and s_info["indexed"]:
                                    st.session_state.v_manager.remove_document(item["name"], s_name)
                                    st.session_state.kb_inventory[idx]["sheets"][s_name]["indexed"] = False
                    
                    st.success("Vector Store synced!")
                    st.rerun()
        
        if col_btn2.button("🧹 Clear All", use_container_width=True):
            st.session_state.kb_inventory = []
            st.session_state.v_manager = VectorStoreManager()
            st.rerun()

        # Navigation to Next Step
        has_indexed_content = False
        for item in st.session_state.kb_inventory:
            if item["type"] == "pdf" and item.get("indexed"):
                has_indexed_content = True
                break
            elif item["type"] == "excel" and any(s.get("indexed") for s in item.get("sheets", {}).values()):
                has_indexed_content = True
                break
        
        if has_indexed_content:
            st.divider()
            if st.button("Next: Configure Mapping ➡️", type="secondary", use_container_width=True):
                st.session_state.step = 2
                st.rerun()

    # Navigation to Next Step
    if st.session_state.kb_inventory:
        st.divider()
        c_nav1, c_nav2 = st.columns([4, 1])
        with c_nav2:
            if st.button("Next: Configure Mapping ➡️", type="primary"):
                st.session_state.step = 2
                st.rerun()

# Step 2: Mapping Configuration
elif st.session_state.step == 2:
    st.header("Configure Mapping Document")
    
    if not st.session_state.kb_inventory:
        st.warning("⚠️ Please upload and submit a Knowledge Base in Step 1 first.")
    
    mapping_file = st.file_uploader("Upload Mapping Excel", type=["xlsx"], key="map_uploader")
    
    if mapping_file:
        file_bytes = mapping_file.read()
        sheets = get_excel_sheets(file_bytes)
        selected_map_sheet = st.selectbox("Select Mapping Sheet", sheets, key="map_sheet_selector")
        
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_map_sheet)
        st.session_state.mapping_df = df
        st.write("Preview of Uploaded Mapping:")
        st.dataframe(df.head())
        
        st.divider()
        st.subheader("Map Columns (Use Column Letters A, B, C or Names)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Source Fields")
            # Using keys ensures persistence across reruns/steps
            s_subj = st.text_input("Subject Area Column", placeholder="e.g. A", key="map_s_subj")
            s_db = st.text_input("DB Name Column", placeholder="e.g. B", key="map_s_db")
            s_tbl = st.text_input("Table Name Column", placeholder="e.g. C", key="map_s_tbl")
            s_col = st.text_input("Column Name Column", placeholder="e.g. D", key="map_s_col")
            s_type = st.text_input("Datatype Column", placeholder="e.g. E", key="map_s_type")
            
        with col2:
            st.markdown("### Target Fields")
            t_subj = st.text_input("Target Subject Area", placeholder="e.g. F", key="map_t_subj")
            t_db = st.text_input("Target DB Name", placeholder="e.g. G", key="map_t_db")
            t_tbl = st.text_input("Target Table Name", placeholder="e.g. H", key="map_t_tbl")
            t_col = st.text_input("Target Column Name", placeholder="e.g. I", key="map_t_col")
            t_type = st.text_input("Target Datatype", placeholder="e.g. J", key="map_t_type")

        st.subheader("Row Range")
        c_r1, c_r2 = st.columns(2)
        # Replacing slider with number inputs for better control
        r_start = c_r1.number_input("Start Row", min_value=1, max_value=len(df), value=1, key="map_r_start")
        r_end = c_r2.number_input("End Row", min_value=1, max_value=len(df), value=min(10, len(df)), key="map_r_end")

        if st.button("Preview Mapping"):
            st.session_state.show_mapping_preview = True
            st.rerun()

    # Preview Section (Appears below inputs)
    if st.session_state.get("show_mapping_preview") and st.session_state.mapping_df is not None:
        st.divider()
        st.header("Preview & Process")
        
        # Save config from persistent keys
        st.session_state.mapping_config = {
            "source": {
                "subj": st.session_state.map_s_subj, 
                "db": st.session_state.map_s_db, 
                "tbl": st.session_state.map_s_tbl, 
                "col": st.session_state.map_s_col, 
                "type": st.session_state.map_s_type
            },
            "target": {
                "subj": st.session_state.map_t_subj, 
                "db": st.session_state.map_t_db, 
                "tbl": st.session_state.map_t_tbl, 
                "col": st.session_state.map_t_col, 
                "type": st.session_state.map_t_type
            },
            "range": (st.session_state.map_r_start, st.session_state.map_r_end)
        }
        
        df = st.session_state.mapping_df
        conf = st.session_state.mapping_config
        r_start, r_end = conf["range"]
        
        def get_val(row, col_identifier):
            if not col_identifier: return "N/A"
            # 1. Try as direct column name
            if col_identifier in row.index:
                return str(row[col_identifier])
            
            # 2. Try as Excel letter (A, B, C...)
            idx = excel_col_to_idx(col_identifier)
            if idx is not None and 0 <= idx < len(row):
                return str(row.iloc[idx])
                
            return "N/A"

        processed_rows = []
        if r_start > r_end:
            st.error("Start Row must be less than or equal to End Row.")
        else:
            for idx in range(r_start-1, r_end):
                if idx >= len(df): break
                row = df.iloc[idx]
                processed_rows.append({
                    "Source": f"{get_val(row, conf['source']['db'])}.{get_val(row, conf['source']['tbl'])}.{get_val(row, conf['source']['col'])}",
                    "Target": f"{get_val(row, conf['target']['db'])}.{get_val(row, conf['target']['tbl'])}.{get_val(row, conf['target']['col'])}"
                })
            
            st.table(processed_rows)
            
            if st.button("Generate Mappings", type="primary"):
                results = []
                progress_bar = st.progress(0)
                
                base_url = st.session_state.get("base_url")
                api_key = st.session_state.get("api_key")
                model_name = st.session_state.get("selected_model", "gpt-4o")
                
                agent = create_agent(
                    st.session_state.v_manager.get_retriever(),
                    model_name=model_name,
                    api_key=api_key,
                    base_url=base_url
                )
                
                total_rows = r_end - r_start + 1
                for i, idx in enumerate(range(r_start-1, r_end)):
                    if idx >= len(df): break
                    row = df.iloc[idx]
                    source_info = {
                        "subject_area": get_val(row, conf['source']['subj']),
                        "db_name": get_val(row, conf['source']['db']),
                        "table_name": get_val(row, conf['source']['tbl']),
                        "column_name": get_val(row, conf['source']['col']),
                        "datatype": get_val(row, conf['source']['type'])
                    }
                    target_info = {
                        "subject_area": get_val(row, conf['target']['subj']),
                        "db_name": get_val(row, conf['target']['db']),
                        "table_name": get_val(row, conf['target']['tbl']),
                        "column_name": get_val(row, conf['target']['col']),
                        "datatype": get_val(row, conf['target']['type'])
                    }
                    
                    with st.spinner(f"Processing row {idx+1}..."):
                        res = agent.invoke({
                            "source_info": source_info,
                            "target_info": target_info,
                            "context": "",
                            "transformation_type": "",
                            "transformation_logic": "",
                            "reasoning": ""
                        })
                        results.append({
                            "row_idx": idx + 1,
                            "source_info": source_info,
                            "target_info": target_info,
                            **res
                        })
                    progress_bar.progress((i + 1) / total_rows)
                    
                st.session_state.results = results
                st.session_state.step = 3 # Move to Results
                st.rerun()

# Step 3: Results
elif st.session_state.step == 3:
    st.header("Transformation Results")
    
    if not st.session_state.results:
        st.warning("⚠️ No results generated yet. Please run the generation in Step 2.")
    else:
        results = st.session_state.results
        
        def on_regenerate(row_idx):
            # Find the result entry
            for i, res in enumerate(st.session_state.results):
                if res["row_idx"] == row_idx:
                    # Get LLM config from session state
                    base_url = st.session_state.get("base_url")
                    api_key = st.session_state.get("api_key")
                    model_name = st.session_state.get("selected_model", "gpt-4o")
                    
                    agent = create_agent(
                        st.session_state.v_manager.get_retriever(),
                        model_name=model_name,
                        api_key=api_key,
                        base_url=base_url
                    )
                    new_res = agent.invoke({
                        "source_info": res["source_info"],
                        "target_info": res["target_info"],
                        "context": "",
                        "transformation_type": "",
                        "transformation_logic": "",
                        "reasoning": "",
                        "feedback": st.session_state.get(f"feedback_{row_idx}", "")
                    })
                    st.session_state.results[i].update(new_res)
                    st.success(f"Row {row_idx} regenerated!")
                    break

        for res in results:
            with st.expander(f"Row {res['row_idx']}: {res['source_info']['column_name']} -> {res['target_info']['column_name']}", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Type", res['transformation_type'])
                c2.code(res['transformation_logic'], language="sql")
                c3.info(res['reasoning'])
                
                feedback = st.text_input("Add feedback for regeneration", key=f"feedback_{res['row_idx']}")
                if st.button("Regenerate", key=f"btn_{res['row_idx']}"):
                    on_regenerate(res['row_idx'])
                    st.rerun()

        # Option to export to Excel
        if results:
            final_df = pd.DataFrame(results)
            # Flatten source/target info if needed for excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False, sheet_name='Mappings')
            
            st.download_button(
                label="Download Results as Excel",
                data=buffer.getvalue(),
                file_name="mapping_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
