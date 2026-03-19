import os
import shutil
import json
import pandas as pd
from typing import List, Dict, Any, Optional
import io

PROJECTS_DIR = "projects"

class ProjectManager:
    @staticmethod
    def list_projects() -> List[str]:
        if not os.path.exists(PROJECTS_DIR):
            os.makedirs(PROJECTS_DIR)
        return [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]

    @staticmethod
    def create_project(name: str) -> bool:
        path = os.path.join(PROJECTS_DIR, name)
        if os.path.exists(path):
            return False
        os.makedirs(path)
        os.makedirs(os.path.join(path, "files"))
        os.makedirs(os.path.join(path, "vector_store"))
        return True

    @staticmethod
    def delete_project(name: str) -> bool:
        path = os.path.join(PROJECTS_DIR, name)
        if os.path.exists(path):
            shutil.rmtree(path)
            return True
        return False

    @staticmethod
    def get_project_path(name: str) -> str:
        return os.path.join(PROJECTS_DIR, name)

    @staticmethod
    def save_file(project_name: str, filename: str, file_bytes: bytes) -> str:
        """Saves a file to the project's files directory."""
        path = os.path.join(PROJECTS_DIR, project_name, "files", filename)
        with open(path, "wb") as f:
            f.write(file_bytes)
        return path

    @staticmethod
    def load_file(project_name: str, filename: str) -> Optional[bytes]:
        """Loads a file from the project's files directory."""
        path = os.path.join(PROJECTS_DIR, project_name, "files", filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return None

    @staticmethod
    def delete_file(project_name: str, filename: str) -> bool:
        path = os.path.join(PROJECTS_DIR, project_name, "files", filename)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    @staticmethod
    def save_metadata(project_name: str, metadata: Dict[str, Any]):
        path = os.path.join(PROJECTS_DIR, project_name, "metadata.json")
        with open(path, "w") as f:
            json.dump(metadata, f, indent=4)

    @staticmethod
    def load_metadata(project_name: str) -> Dict[str, Any]:
        path = os.path.join(PROJECTS_DIR, project_name, "metadata.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def update_metadata(project_name: str, updates: Dict[str, Any]):
        """Merges updates into existing metadata and saves."""
        meta = ProjectManager.load_metadata(project_name)
        meta.update(updates)
        ProjectManager.save_metadata(project_name, meta)
    
    @staticmethod
    def save_dataframe(project_name: str, filename: str, df: pd.DataFrame):
        path = os.path.join(PROJECTS_DIR, project_name, filename)
        # Using Excel for now as that seems to be the preferred format in this app
        if filename.endswith(".xlsx"):
            df.to_excel(path, index=False)
        elif filename.endswith(".csv"):
            df.to_csv(path, index=False)
            
    @staticmethod
    def load_dataframe(project_name: str, filename: str) -> Optional[pd.DataFrame]:
        path = os.path.join(PROJECTS_DIR, project_name, filename)
        if os.path.exists(path):
            if filename.endswith(".xlsx"):
                return pd.read_excel(path)
            elif filename.endswith(".csv"):
                return pd.read_csv(path)
        return None
