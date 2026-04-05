import streamlit as st
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from .vector_store import VectorStoreManager
from .project_manager import ProjectManager
import pandas as pd
import os
import copy

class AppState:
    """
    Manages Streamlit session state directly backed by file storage.
    """
    
    PERSISTENT_KEYS = [
        "current_project",
        "step", "kb_inventory", "fsdm_inventory", "mapping_df", "mapping_config", 
        "results", "logs", "show_mapping_preview",
        "base_url", "api_key", "selected_model", "available_models", "agent_mode",
        "map_s_subj", "map_s_db", "map_s_tbl", "map_s_col", "map_s_type",
        "map_t_subj", "map_t_db", "map_t_tbl", "map_t_col", "map_t_type",
        "map_trans_type", "map_trans_cond", "map_remarks",
        "map_r_start", "map_r_end", "map_sheet_selector",
        "auto_scroll", "mapping_active", "mapping_idx"
    ]

    def __init__(self):
        self._init_defaults()

    def _init_defaults(self):
        defaults = {
            "current_project": None,
            "step": 1,
            "kb_inventory": [],
            "fsdm_inventory": [],
            "results": [],
            "logs": [],
            "show_mapping_preview": False,
            "base_url": "",
            "api_key": "",
            "selected_model": "gpt-4o",
            "available_models": [],
            "agent_mode": "One-shot",
            "map_s_subj": "", "map_s_db": "", "map_s_tbl": "", "map_s_col": "", "map_s_type": "",
            "map_t_subj": "", "map_t_db": "", "map_t_tbl": "", "map_t_col": "", "map_t_type": "",
            "map_trans_type": "", "map_trans_cond": "", "map_remarks": "",
            "map_r_start": 1,
            "map_r_end": 10,
            "auto_scroll": True,
            "mapping_active": False,
            "mapping_idx": 0
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v
        
        # If we have an active project, ensure st.session_state is populated from metadata
        # This handles cases where Streamlit purges keys for non-rendered widgets
        curr_proj = st.session_state.get("current_project")
        if curr_proj:
            meta = ProjectManager.load_metadata(curr_proj)
            for k in self.PERSISTENT_KEYS:
                # If key is in meta but missing from session_state, restore it.
                # We ONLY restore if the key is missing from session_state.
                # If it's present but None, it might be owned by an active widget.
                if k in meta and k not in st.session_state:
                    # For kb_inventory, we don't re-hydrate bytes here to avoid overhead
                    # unless it's explicitly needed. But simple strings/ints are fine.
                    if k not in ["kb_inventory", "fsdm_inventory"]: 
                        st.session_state[k] = meta[k]

        # Objects that don't serialize easily to storage
        if "v_manager" not in st.session_state:
            st.session_state.v_manager = VectorStoreManager()
        if "mapping_df" not in st.session_state:
            st.session_state.mapping_df = None

    def load_project(self, project_name: str):
        self.current_project = project_name
        
        # Load metadata
        meta = ProjectManager.load_metadata(project_name)
        
        # Restore keys
        for k, v in meta.items():
            if k in ["kb_inventory", "fsdm_inventory"]:
                 # Re-hydrate bytes
                 for item in v:
                     if "name" in item:
                         b = ProjectManager.load_file(project_name, item["name"])
                         if b:
                             item["bytes"] = b
            
            if k in self.PERSISTENT_KEYS:
                st.session_state[k] = v

        # Load Mapping DF
        df = ProjectManager.load_dataframe(project_name, "mapping.xlsx")
        self.mapping_df = df
        
        # Initialize Vector Store
        project_path = ProjectManager.get_project_path(project_name)
        vs_path = os.path.join(project_path, "vector_store")
        
        st.session_state.v_manager = VectorStoreManager(persist_directory=vs_path)
        st.session_state.v_manager.initialize_store()

    def save_project(self):
        if not self.current_project:
            return

        updates = {}
        for k in self.PERSISTENT_KEYS:
            # Skip mapping_df in JSON (it's saved as a file)
            if k == "mapping_df":
                continue

            # Only update if the key is actually in session_state.
            # This prevents Streamlit's widget cleanup from deleting our persistent data
            # when switching between steps or rendering conditionally.
            if k in st.session_state:
                val = st.session_state[k]

                if k in ["kb_inventory", "fsdm_inventory"] and val:
                    # Don't save large bytes to metadata.json
                    val_copy = copy.deepcopy(val)
                    for item in val_copy:
                        if "bytes" in item:
                            del item["bytes"]
                    updates[k] = val_copy
                else:
                    updates[k] = val

        if updates:
            ProjectManager.update_metadata(self.current_project, updates)

        # Save Mapping DF separately
        if self.mapping_df is not None:
             ProjectManager.save_dataframe(self.current_project, "mapping.xlsx", self.mapping_df)

    def sync(self):
        """
        Alias for save_project to maintain compatibility.
        """
        self.save_project()

    @property
    def agent_mode(self) -> str:
        return st.session_state.get("agent_mode", "One-shot")

    @agent_mode.setter
    def agent_mode(self, value: str):
        st.session_state["agent_mode"] = value
        self.save_project()

    @property
    def current_project(self) -> Optional[str]:
        return st.session_state.get("current_project")

    @current_project.setter
    def current_project(self, value: Optional[str]):
        st.session_state["current_project"] = value

    @property
    def step(self) -> int:
        return st.session_state.get("step", 1)

    @step.setter
    def step(self, value: int):
        st.session_state["step"] = value
        self.save_project()

    # Mapping Configuration Properties for easier access and reliability
    @property
    def map_s_subj(self): return st.session_state.get("map_s_subj", "")
    @property
    def map_s_db(self): return st.session_state.get("map_s_db", "")
    @property
    def map_s_tbl(self): return st.session_state.get("map_s_tbl", "")
    @property
    def map_s_col(self): return st.session_state.get("map_s_col", "")
    @property
    def map_s_type(self): return st.session_state.get("map_s_type", "")

    @property
    def map_t_subj(self): return st.session_state.get("map_t_subj", "")
    @property
    def map_t_db(self): return st.session_state.get("map_t_db", "")
    @property
    def map_t_tbl(self): return st.session_state.get("map_t_tbl", "")
    @property
    def map_t_col(self): return st.session_state.get("map_t_col", "")
    @property
    def map_t_type(self): return st.session_state.get("map_t_type", "")

    @property
    def map_trans_type(self): return st.session_state.get("map_trans_type", "")
    @property
    def map_trans_cond(self): return st.session_state.get("map_trans_cond", "")
    @property
    def map_remarks(self): return st.session_state.get("map_remarks", "")

    @property
    def map_r_start(self): return st.session_state.get("map_r_start", 1)
    @property
    def map_r_end(self): return st.session_state.get("map_r_end", 10)

    @property
    def kb_inventory(self) -> List[Dict[str, Any]]:

        return st.session_state.get("kb_inventory", [])

    @kb_inventory.setter
    def kb_inventory(self, value: List[Dict[str, Any]]):
        st.session_state["kb_inventory"] = value
        # We don't auto-save here because kb_inventory changes often involve complex ops
        # Caller usually saves. But to be safe per user request:
        self.save_project()

    @property
    def fsdm_inventory(self) -> List[Dict[str, Any]]:
        return st.session_state.get("fsdm_inventory", [])

    @fsdm_inventory.setter
    def fsdm_inventory(self, value: List[Dict[str, Any]]):
        st.session_state["fsdm_inventory"] = value
        self.save_project()

    @property
    def v_manager(self) -> VectorStoreManager:
        return st.session_state.v_manager

    @property
    def mapping_df(self) -> Optional[pd.DataFrame]:
        return st.session_state.mapping_df

    @mapping_df.setter
    def mapping_df(self, value: Optional[pd.DataFrame]):
        st.session_state.mapping_df = value
        self.save_project()

    @property
    def results(self) -> List[Dict[str, Any]]:
        return st.session_state.get("results", [])

    @results.setter
    def results(self, value: List[Dict[str, Any]]):
        st.session_state["results"] = value
        self.save_project()

    @property
    def mapping_active(self) -> bool:
        return st.session_state.get("mapping_active", False)

    @mapping_active.setter
    def mapping_active(self, value: bool):
        st.session_state["mapping_active"] = value

    # @property
    # def mapping_active(self) -> bool:
    #     return st.session_state.get("mapping_active", False)

    @mapping_active.setter
    def mapping_active(self, value: bool):
        st.session_state["mapping_active"] = value
        self.save_project()

    @property
    def mapping_idx(self) -> int:
        return st.session_state.get("mapping_idx", 0)

    @mapping_idx.setter
    def mapping_idx(self, value: int):
        st.session_state["mapping_idx"] = value
        self.save_project()

    @property
    def auto_scroll(self) -> bool:
        return st.session_state.get("auto_scroll", True)

    @auto_scroll.setter
    def auto_scroll(self, value: bool):
        st.session_state["auto_scroll"] = value
        self.save_project()

    @property
    def logs(self) -> List[str]:
        return st.session_state.get("logs", [])

    def add_log(self, message: str):
        logs = self.logs
        logs.append(message)
        if len(logs) > 100:
            logs.pop(0)
        st.session_state["logs"] = logs
        # Logging is frequent, maybe don't auto-save every log line to disk to avoid perf hit?
        # User said "Every update goes to file".
        self.save_project()

    def clear_logs(self):
        st.session_state["logs"] = []
        self.save_project()

    def reset_kb(self):
        self.kb_inventory = []
        self.fsdm_inventory = []
        st.session_state.v_manager = VectorStoreManager()
        self.results = []
        self.clear_logs()
        self.mapping_df = None
        st.session_state.show_mapping_preview = False
        # Clear storage keys for mapping
        for k in self.PERSISTENT_KEYS:
            if k.startswith("map_"):
                st.session_state[k] = 1 if "start" in k or "end" in k else ""
        self.save_project()

    def get_llm_config(self) -> Dict[str, Any]:
        return {
            "base_url": st.session_state.get("base_url", ""),
            "api_key": st.session_state.get("api_key", ""),
            "model_name": st.session_state.get("selected_model", "")
        }
