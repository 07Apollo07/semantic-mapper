import pandas as pd
from typing import List, Dict, Any, Callable
from agent import create_agent
from .utils import excel_col_to_idx

class MappingEngine:
    """Core logic for running the semantic mapping process."""
    
    def __init__(self, state, progress_callback: Callable[[float], None] = None, log_callback: Callable[[str], None] = None):
        self.state = state
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.agent = None

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        self.state.add_log(message)

    def initialize_agent(self):
        llm_config = self.state.get_llm_config()
        self._log(f"Initializing agent with model: {llm_config['model_name']}")
        
        retriever = self.state.v_manager.get_retriever()
        self.agent = create_agent(
            retriever,
            model_name=llm_config["model_name"],
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
            log_callback=self._log
        )

    def get_cell_value(self, row, col_identifier):
        if not col_identifier: return "N/A"
        
        # 1. Try as direct column name
        if col_identifier in row.index:
            return str(row[col_identifier])
        
        # 2. Try as Excel letter (A, B, C...)
        idx = excel_col_to_idx(col_identifier)
        if idx is not None and 0 <= idx < len(row):
            return str(row.iloc[idx])
            
        return "N/A"

    def run(self, r_start: int, r_end: int):
        df = self.state.mapping_df
        conf = self.state.mapping_config
        
        if self.agent is None:
            self.initialize_agent()
            
        results = []
        total_rows = r_end - r_start + 1
        
        for i, idx in enumerate(range(r_start - 1, r_end)):
            if idx >= len(df): break
            
            row = df.iloc[idx]
            source_info = {
                "subject_area": self.get_cell_value(row, conf['source']['subj']),
                "db_name": self.get_cell_value(row, conf['source']['db']),
                "table_name": self.get_cell_value(row, conf['source']['tbl']),
                "column_name": self.get_cell_value(row, conf['source']['col']),
                "datatype": self.get_cell_value(row, conf['source']['type'])
            }
            target_info = {
                "subject_area": self.get_cell_value(row, conf['target']['subj']),
                "db_name": self.get_cell_value(row, conf['target']['db']),
                "table_name": self.get_cell_value(row, conf['target']['tbl']),
                "column_name": self.get_cell_value(row, conf['target']['col']),
                "datatype": self.get_cell_value(row, conf['target']['type'])
            }
            
            transformation_specs = {
                "type": self.get_cell_value(row, conf.get('transformation', {}).get('type')),
                "condition": self.get_cell_value(row, conf.get('transformation', {}).get('cond'))
            }
            
            self._log(f"Processing Row {idx+1}: {source_info['column_name']} -> {target_info['column_name']}")
            
            try:
                res = self.agent.invoke({
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
                self._log(f"✅ Success Row {idx+1}: {res['transformation_type']}")
                
            except Exception as e:
                self._log(f"❌ Error Row {idx+1}: {str(e)}")
                results.append({
                    "row_idx": idx + 1,
                    "source_info": source_info,
                    "target_info": target_info,
                    "transformation_type": "ERROR",
                    "transformation_logic": str(e),
                    "reasoning": "Processing failed."
                })
            
            if self.progress_callback:
                self.progress_callback((i + 1) / total_rows)
        
        self.state.results = results
        return results

    def regenerate_row(self, row_idx: int, feedback: str = ""):
        # Find the result entry in state
        current_results = self.state.results
        found_idx = -1
        for i, res in enumerate(current_results):
            if res["row_idx"] == row_idx:
                found_idx = i
                break
        
        if found_idx == -1:
            self._log(f"⚠️ Cannot find Row {row_idx} in results for regeneration.")
            return

        if self.agent is None:
            self.initialize_agent()

        res = current_results[found_idx]
        self._log(f"Regenerating Row {row_idx} with feedback: {feedback}")
        
        try:
            new_res = self.agent.invoke({
                "source_info": res["source_info"],
                "target_info": res["target_info"],
                "context": "",
                "transformation_type": "",
                "transformation_logic": "",
                "reasoning": "",
                "feedback": feedback
            })
            
            # Update the entry in state
            current_results[found_idx].update(new_res)
            self.state.results = current_results # Trigger state update
            self._log(f"✅ Row {row_idx} regenerated successfully.")
            return True
        except Exception as e:
            self._log(f"❌ Error regenerating Row {row_idx}: {str(e)}")
            return False
