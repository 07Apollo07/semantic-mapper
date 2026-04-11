import os
from agent.tools.tools import vector_tool

# Initialize tools for a test project
project_name = "test_project"
# Assuming we have a test project setup or just want to test if it calls
# Using a dummy project name for now.

print("--- Testing Vector Search Tool ---")
try:
    # Creating a dummy vector_tool that uses project_name
    # The tool is already bound in get_tools in agent/tools.py but we need it here.
    # To keep it simple, I will invoke the underlying function or re-instantiate.
    # Actually, I can just use the provided tools if I correctly import them.
    
    # Simple test invocation
    result = vector_tool.invoke({"query": "sales lineage"})
    print(f"Result: {result}")
except Exception as e:
    print(f"Test failed: {e}")
