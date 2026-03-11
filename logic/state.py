import streamlit as st
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from .vector_store import VectorStoreManager
import pandas as pd

class AppState:
    """
    Manages Streamlit session state with a persistence shadow to prevent 
    Streamlit from clearing widget data when they are not rendered.
    """
    
    PERSISTENT_KEYS = [
        "step", "kb_inventory", "mapping_df", "mapping_config", 
        "results", "logs", "show_mapping_preview",
        "base_url", "api_key", "selected_model", "available_models",
        "map_s_subj", "map_s_db", "map_s_tbl", "map_s_col", "map_s_type",
        "map_t_subj", "map_t_db", "map_t_tbl", "map_t_col", "map_t_type",
        "map_trans_type", "map_trans_cond",
        "map_r_start", "map_r_end", "map_sheet_selector"
    ]

    def __init__(self):
        # 1. Initialize hidden storage if not present
        if "_storage" not in st.session_state:
            st.session_state._storage = {}
        
        # 2. Set defaults in storage if keys are missing
        self._init_defaults()
        
        # 3. Synchronize storage -> session_state
        # This ensures that even if Streamlit deleted a key (because the widget disappeared),
        # we put it back so the next part of the code (or future widgets) can see it.
        for key, val in st.session_state._storage.items():
            if key not in st.session_state:
                st.session_state[key] = val

    def _init_defaults(self):
        defaults = {
            "step": 1,
            "kb_inventory": [],
            "results": [],
            "logs": [],
            "show_mapping_preview": False,
            "base_url": "",
            "api_key": "",
            "selected_model": "gpt-4o",
            "available_models": [],
            "map_s_subj": "", "map_s_db": "", "map_s_tbl": "", "map_s_col": "", "map_s_type": "",
            "map_t_subj": "", "map_t_db": "", "map_t_tbl": "", "map_t_col": "", "map_t_type": "",
            "map_trans_type": "", "map_trans_cond": "",
            "map_r_start": 1,
            "map_r_end": 10
        }
        for k, v in defaults.items():
            if k not in st.session_state._storage:
                st.session_state._storage[k] = v
        
        # Objects that don't serialize easily to storage sometimes stay in session_state root
        if "v_manager" not in st.session_state:
            st.session_state.v_manager = VectorStoreManager()
        if "mapping_df" not in st.session_state:
            st.session_state.mapping_df = None

    def sync(self):
        """
        Call this at the end of the script or after significant input changes.
        It saves current session_state values back into the persistent storage.
        """
        for key in self.PERSISTENT_KEYS:
            if key in st.session_state:
                st.session_state._storage[key] = st.session_state[key]

    @property
    def step(self) -> int:
        return st.session_state._storage.get("step", 1)

    @step.setter
    def step(self, value: int):
        st.session_state._storage["step"] = value
        st.session_state.step = value # Sync immediately

    @property
    def kb_inventory(self) -> List[Dict[str, Any]]:
        return st.session_state._storage.get("kb_inventory", [])

    @kb_inventory.setter
    def kb_inventory(self, value: List[Dict[str, Any]]):
        st.session_state._storage["kb_inventory"] = value
        st.session_state.kb_inventory = value

    @property
    def v_manager(self) -> VectorStoreManager:
        return st.session_state.v_manager

    @property
    def mapping_df(self) -> Optional[pd.DataFrame]:
        return st.session_state.mapping_df

    @mapping_df.setter
    def mapping_df(self, value: Optional[pd.DataFrame]):
        st.session_state.mapping_df = value

    @property
    def results(self) -> List[Dict[str, Any]]:
        return st.session_state._storage.get("results", [])

    @results.setter
    def results(self, value: List[Dict[str, Any]]):
        st.session_state._storage["results"] = value
        st.session_state.results = value

    @property
    def logs(self) -> List[str]:
        return st.session_state._storage.get("logs", [])

    def add_log(self, message: str):
        logs = self.logs
        logs.append(message)
        if len(logs) > 100:
            logs.pop(0)
        st.session_state._storage["logs"] = logs
        st.session_state.logs = logs

    def clear_logs(self):
        st.session_state._storage["logs"] = []
        st.session_state.logs = []

    def reset_kb(self):
        self.kb_inventory = []
        st.session_state.v_manager = VectorStoreManager()
        self.results = []
        self.clear_logs()
        self.mapping_df = None
        st.session_state.show_mapping_preview = False
        # Clear storage keys for mapping
        for k in self.PERSISTENT_KEYS:
            if k.startswith("map_"):
                st.session_state._storage[k] = 1 if "start" in k or "end" in k else ""

    def get_llm_config(self) -> Dict[str, Any]:
        return {
            "base_url": st.session_state._storage.get("base_url", ""),
            "api_key": st.session_state._storage.get("api_key", ""),
            "model_name": st.session_state._storage.get("selected_model", "gpt-4o")
        }
