import pandas as pd
from typing import Dict, Any, List, Optional
from agent.graph import create_agent
from logic.utils import get_cell_value

class AgentExecutor:
    """
    Handles synchronous, row-by-row agent execution for both batch mapping 
    and single-row regeneration.
    """

    def __init__(self, state):
        self.state = state
        self.agent = None
        self._initialize_agent()

    def _initialize_agent(self):
        llm_config = self.state.get_llm_config()
        retriever = self.state.v_manager.get_retriever()
        
        self.agent = create_agent(
            retriever,
            model_name=llm_config["model_name"],
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
            log_callback=self._log
        )

    def _log(self, message: str):
        # Always log to state and print to console for "real-time" visibility
        self.state.add_log(message)
        print(message)

    def extract_row_info(self, row: pd.Series, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts source, target, and transformation info from a dataframe row."""
        s = config.get("source", {})
        t = config.get("target", {})
        tr = config.get("transformation", {})

        source_info = {
            "subject_area": get_cell_value(row, s.get("subj")),
            "db_name": get_cell_value(row, s.get("db")),
            "table_name": get_cell_value(row, s.get("tbl")),
            "column_name": get_cell_value(row, s.get("col")),
            "datatype": get_cell_value(row, s.get("type"))
        }
        target_info = {
            "subject_area": get_cell_value(row, t.get("subj")),
            "db_name": get_cell_value(row, t.get("db")),
            "table_name": get_cell_value(row, t.get("tbl")),
            "column_name": get_cell_value(row, t.get("col")),
            "datatype": get_cell_value(row, t.get("type"))
        }
        transformation_specs = {
            "type": get_cell_value(row, tr.get("type")),
            "condition": get_cell_value(row, tr.get("cond"))
        }

        return {
            "source_info": source_info,
            "target_info": target_info,
            "transformation_specs": transformation_specs
        }

    def process_row(self, row_data: Dict[str, Any], row_idx: int, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Invokes the agent for a single row of data."""
        self._log(f"Processing Row {row_idx}: {row_data['source_info'].get('column_name')} -> {row_data['target_info'].get('column_name')}")
        
        try:
            inputs = {
                **row_data,
                "context": "",
                "transformation_type": "",
                "transformation_logic": "",
                "reasoning": ""
            }
            if feedback:
                inputs["feedback"] = feedback

            res = self.agent.invoke(inputs)
            
            self._log(f"✅ Success Row {row_idx}: {res['transformation_type']}")
            return {
                "row_idx": row_idx,
                "source_info": row_data["source_info"],
                "target_info": row_data["target_info"],
                **res
            }
        except Exception as e:
            self._log(f"❌ Error Row {row_idx}: {str(e)}")
            return {
                "row_idx": row_idx,
                "source_info": row_data["source_info"],
                "target_info": row_data["target_info"],
                "transformation_type": "ERROR",
                "transformation_logic": str(e),
                "reasoning": "Processing failed."
            }

    def run_batch(self, df: pd.DataFrame, config: Dict[str, Any], progress_placeholder=None, status_placeholder=None):
        """Iterates through a range of rows and processes them synchronously."""
        r_range = config.get("range", (1, 10))
        r_start, r_end = r_range
        
        results = []
        total_rows = r_end - r_start + 1
        
        self._log(f"Starting batch mapping for rows {r_start} to {r_end}...")

        for i, idx in enumerate(range(r_start - 1, r_end)):
            if idx >= len(df): break
            
            row = df.iloc[idx]
            row_info = self.extract_row_info(row, config)
            
            if status_placeholder:
                status_placeholder.info(f"Processing Row {idx+1} of {r_end}: {row_info['source_info']['column_name']}...")
            
            result_entry = self.process_row(row_info, idx + 1)
            results.append(result_entry)
            
            if progress_placeholder:
                progress_placeholder.progress((i + 1) / total_rows)
        
        if status_placeholder:
            status_placeholder.success(f"Mapping complete for {len(results)} rows!")
            
        return results
