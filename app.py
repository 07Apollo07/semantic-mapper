import streamlit as st
import pandas as pd
import io
from logic import process_pdf, get_excel_sheets, process_excel_sheets, split_documents, VectorStoreManager
from agent import create_agent
from ui import sidebar_config, step_indicator

st.set_page_config(page_title="Semantic Mapper AI", layout="wide")

# Initialize Session State
if "step" not in st.session_state:
    st.session_state.step = 1
if "kb_docs" not in st.session_state:
    st.session_state.kb_docs = []
if "v_manager" not in st.session_state:
    st.session_state.v_manager = VectorStoreManager()
if "mapping_df" not in st.session_state:
    st.session_state.mapping_df = None
if "mapping_config" not in st.session_state:
    st.session_state.mapping_config = {}
if "results" not in st.session_state:
    st.session_state.results = []

sidebar_config()
st.title("Semantic Mapper AI 🧠")
step_indicator(st.session_state.step)

# Step 1: Knowledge Base Upload
if st.session_state.step == 1:
    st.header("Upload Knowledge Base")
    uploaded_files = st.file_uploader("Upload PDFs or Excel Sheets", accept_multiple_files=True, type=["pdf", "xlsx"])
    
    if uploaded_files:
        all_docs = []
        for file in uploaded_files:
            file_bytes = file.read()
            if file.name.endswith(".pdf"):
                docs = process_pdf(file_bytes, file.name)
                all_docs.extend(docs)
                st.success(f"Processed {file.name}")
            elif file.name.endswith(".xlsx"):
                sheets = get_excel_sheets(file_bytes)
                st.write(f"Select sheets for **{file.name}**:")
                cols = st.columns(len(sheets))
                selected = []
                for i, sheet in enumerate(sheets):
                    if cols[i % len(cols)].checkbox(f"{sheet}", key=f"{file.name}_{sheet}"):
                        selected.append(sheet)
                
                if selected:
                    docs = process_excel_sheets(file_bytes, file.name, selected)
                    all_docs.extend(docs)
                    st.success(f"Added {len(selected)} sheets from {file.name}")
        
        if all_docs:
            if st.button("Submit Knowledge Base"):
                with st.spinner("Indexing documents..."):
                    chunks = split_documents(all_docs)
                    st.session_state.v_manager.initialize_store(chunks)
                    st.session_state.kb_docs = chunks
                    st.session_state.step = 2
                    st.rerun()

# Step 2: Mapping Configuration
elif st.session_state.step == 2:
    st.header("Configure Mapping Document")
    mapping_file = st.file_uploader("Upload Mapping Excel", type=["xlsx"])
    
    if mapping_file:
        file_bytes = mapping_file.read()
        sheets = get_excel_sheets(file_bytes)
        selected_map_sheet = st.selectbox("Select Mapping Sheet", sheets)
        
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_map_sheet)
        st.session_state.mapping_df = df
        st.write("Preview of Uploaded Mapping:")
        st.dataframe(df.head())
        
        st.divider()
        st.subheader("Map Columns (Use Column Letters A, B, C or Names)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Source Fields")
            s_subj = st.text_input("Subject Area Column", placeholder="e.g. SubjectArea")
            s_db = st.text_input("DB Name Column", placeholder="e.g. SourceDB")
            s_tbl = st.text_input("Table Name Column", placeholder="e.g. SourceTable")
            s_col = st.text_input("Column Name Column", placeholder="e.g. SourceColumn")
            s_type = st.text_input("Datatype Column", placeholder="e.g. SourceType")
            
        with col2:
            st.markdown("### Target Fields")
            t_subj = st.text_input("Target Subject Area", placeholder="e.g. TargetSubject")
            t_db = st.text_input("Target DB Name", placeholder="e.g. TargetDB")
            t_tbl = st.text_input("Target Table Name", placeholder="e.g. TargetTable")
            t_col = st.text_input("Target Column Name", placeholder="e.g. TargetColumn")
            t_type = st.text_input("Target Datatype", placeholder="e.g. TargetType")

        row_range = st.slider("Select Row Range to Process", 1, len(df), (1, min(10, len(df))))

        if st.button("Preview Mapping"):
            st.session_state.mapping_config = {
                "source": {"subj": s_subj, "db": s_db, "tbl": s_tbl, "col": s_col, "type": s_type},
                "target": {"subj": t_subj, "db": t_db, "tbl": t_tbl, "col": t_col, "type": t_type},
                "range": row_range
            }
            st.session_state.step = 3
            st.rerun()

# Step 3: Preview & Run
elif st.session_state.step == 3:
    st.header("Preview & Process")
    df = st.session_state.mapping_df
    conf = st.session_state.mapping_config
    r_start, r_end = conf["range"]
    
    # Simple helper to get column value by name or index
    def get_val(row, col_identifier):
        if not col_identifier: return "N/A"
        try:
            return row[col_identifier]
        except KeyError:
            return "N/A"

    processed_rows = []
    for idx in range(r_start-1, r_end):
        row = df.iloc[idx]
        processed_rows.append({
            "Source": f"{get_val(row, conf['source']['db'])}.{get_val(row, conf['source']['tbl'])}.{get_val(row, conf['source']['col'])}",
            "Target": f"{get_val(row, conf['target']['db'])}.{get_val(row, conf['target']['tbl'])}.{get_val(row, conf['target']['col'])}"
        })
    
    st.table(processed_rows)
    
    if st.button("Generate Mappings"):
        results = []
        progress_bar = st.progress(0)
        
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
        
        for i, idx in enumerate(range(r_start-1, r_end)):
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
            progress_bar.progress((i + 1) / (r_end - r_start + 1))
            
        st.session_state.results = results
        st.session_state.step = 4
        st.rerun()

# Step 4: Results
elif st.session_state.step == 4:
    st.header("Transformation Results")
    
    if st.button("Back to Config"):
        st.session_state.step = 2
        st.rerun()

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
