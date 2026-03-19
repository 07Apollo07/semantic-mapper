import os
from logic.project_manager import ProjectManager
from logic.state import AppState
import shutil
import streamlit as st

# Mock streamlit session state
class MockSessionState(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'MockSessionState' object has no attribute '{key}'")
    
    def __setattr__(self, key, value):
        self[key] = value

if not hasattr(st, "session_state"):
    st.session_state = MockSessionState()

def test_project_flow():
    proj_name = "TestProj"
    
    # Clean up if exists
    if os.path.exists(f"projects/{proj_name}"):
        ProjectManager.delete_project(proj_name)

    print("Creating project...")
    assert ProjectManager.create_project(proj_name) == True
    assert os.path.exists(f"projects/{proj_name}")
    assert os.path.exists(f"projects/{proj_name}/files")

    print("Saving file...")
    dummy_content = b"Hello World"
    ProjectManager.save_file(proj_name, "test.txt", dummy_content)
    loaded_content = ProjectManager.load_file(proj_name, "test.txt")
    assert loaded_content == dummy_content
    print("File IO worked.")

    print("Testing AppState persistence...")
    # Initialize state
    state = AppState()
    state.current_project = proj_name
    state.kb_inventory = [{"name": "test.txt", "type": "pdf", "bytes": dummy_content}]
    state.save_project()
    
    # Reset state
    st.session_state = MockSessionState()
    
    # Load state
    new_state = AppState()
    new_state.load_project(proj_name)
    
    assert new_state.current_project == proj_name
    assert len(new_state.kb_inventory) == 1
    assert new_state.kb_inventory[0]["name"] == "test.txt"
    assert new_state.kb_inventory[0]["bytes"] == dummy_content
    print("AppState persistence worked.")

    print("Deleting project...")
    ProjectManager.delete_project(proj_name)
    assert not os.path.exists(f"projects/{proj_name}")
    print("Deletion worked.")

if __name__ == "__main__":
    try:
        test_project_flow()
        print("✅ All tests passed!")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
