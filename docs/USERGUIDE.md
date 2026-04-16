# Semantic Mapper AI - User Guide 📖

This guide provides a comprehensive walkthrough of the Semantic Mapper AI, explaining how to set up your environment, manage data, and orchestrate the agentic mapping workflow.

---

## 1. Core Architecture & Persistence
Semantic Mapper AI is designed for **long-term persistence**.

*   **Project Storage**: Creating a project generates a local directory: `projects/<project_name>/`.
*   **Local File System**: Your uploaded files are organized into specific sub-folders for isolation:
    *   `projects/<name>/files/vs/`: Source documents for the Vector Store.
    *   `projects/<name>/files/fsdm/`: Target FSDM/ETL schema models.
    *   `projects/<name>/files/mapping/`: Source-to-target mapping spreadsheets.
*   **State Management**: All UI states, configurations, and inventory data are saved to `projects/<name>/metadata.json`. This is handled by `project_manager.py`, ensuring that when you reload the app or switch projects, everything remains exactly where you left it.

---

## 2. LLM & Embedding Setup
Before starting, you must configure the LLM Endpoint via the sidebar.

1.  **Base URL**: Enter your LLM provider's endpoint. The system automatically queries the `/v1/models` endpoint to populate the model list.
2.  **Model Selection**: Fetch and select the specific model you wish to use for the Detective and Engineer agents.
3.  **Embedding Model**: Click **Load Embedding Model** to download the required transformer models from **HuggingFace**. These models run locally to power the semantic search in your Knowledge Base.

---

## 3. Building the Knowledge Base
The Knowledge Base (KB) provides the context the agents need to understand your data.

### 3.1 Unstructured Data (Section 1)
Upload PDFs or Excel guides that describe your business logic. After uploading, click **Sync with Vector Store** to index them. This creates a searchable database in `projects/<name>/vector_store/`.

### 3.2 Target Schema & Metadata (Section 1.2)
Upload your target data models (FSDM/ETL sheets).
*   **Merge Headers**: If your Excel sheet has multi-row headers, check this option before syncing.
*   **Generate Metadata**: Click this to have the AI analyze the table and generate a description. 
    *   *Tip*: To customize the prompt used for this, refer to `agent/agents/fsdm_metadata.py`.

---

## 4. Defining the Mapping Universe
Everything done till now and this is a one-time setup activity where you define the scope of your mapping project.

1.  **Upload Mapping Sheets**: Upload your source mapping documents. (Note: Currently, these cannot be removed from the UI once uploaded).
2.  **Multi-Sheet Support**: You can select multiple sheets (e.g., Fact tables, Dimension tables) to be part of your "Universe."
3.  **Column Mapping**: For each sheet, define which columns contain the Subject Area, DB Name, Table, Column, and Datatype.
4.  **Save & Preview**: Save the configuration to see a preview of how the data will be interpreted.
5.  **Sync to Master**: Once all sheets are configured, click **Sync Mappings to Master** to create a consolidated view of all potential mappings. This is stored in the project's SQLite database as the `unified_mapping_view`.

---

## 5. Execution: The Mapping Tree
Now that your universe is defined, you decide what to process.

*   **The Selection Tree**: This hierarchy allows you to drill down from File -> Sheet -> Table -> Row.
*   **Flexible Scope**: You can select a single row for a quick test, or select multiple entire tables for a batch run.
*   **Generate**: Click **Generate SQL Mappings** to start the agents.

---

## 6. Reviewing Results & Exporting
As the agents work, you can monitor the logs in real-time.

*   **View Results**: Use the table selector in **Section 3** to filter results by their target table.
*   **Analyze Reasoning**: Each result includes the "Detective's" discovery report and the "Engineer's" SQL reasoning.
*   **Feedback & Verification**: Provide feedback to regenerate logic or mark a row as "Verified" (Golden Example).
*   **Export**: Once satisfied, click **Export All Processed Tables to Excel** to get a consolidated final report.

---

## 7. Future Roadmap
*   **Enhanced Output Views**: We plan to split Section 3 into two distinct areas:
    1.  **Current Run**: Showing only the outputs from your most recent execution.
    2.  **Project History**: The current view showing all completed mappings across the project.
*   **UI Cleanup**: Adding the ability to remove mapping sheets from the dashboard.

---

## 8. Technical Walkthrough: Logic & Agents 🧠

To extend or customize the system, here is how the core logic and AI layers are structured.

### 8.1 The `logic/` Folder (Backend Engine)
All heavy lifting is decoupled from the Streamlit UI and resides in the `logic/` directory:
*   **`project_manager.py`**: The heart of the system. It handles folder creation, SQLite database initialization, and state persistence via `metadata.json`.
*   **`fsdm/`, `mapping/`, `vector_store/`**: Specialized sub-directories that handle the lifecycle of their respective data types, ensuring the UI remains "thin" and focused only on presentation.

### 8.2 Agent Architecture & Prompts
The application uses two primary agents residing in `agent/agents/`:

1.  **🕵️ FSDM Detective (`fsdm_detective.py`)**: 
    *   **Purpose**: Investigates lineage using structured SQLite tables.
    *   **Prompt Modification**: Change the `state['system_prompt']` inside the `detective_node` function.
    *   **Tools**: Uses `lg_get_table_schema`, `lg_query_db`, and `lg_list_fsdm_tables_logic` to autonomously query the mapping universe.

2.  **⚙️ Mapping Engineer (`mapping_oneshot.py`)**: 
    *   **Purpose**: Consolidates the Detective's findings and vector context into final SQL logic.
    *   **Prompt Modification**: Update the `system_prompt` and `user_content` strings in the `generate_transformation` function.
    *   **Tools**: Primarily uses the **Vector Store Retriever** to pull unstructured documentation context.

### 8.3 Tools & Metadata Generation
*   **Metadata Generation**: The "Generate Metadata" button in the UI uses the logic in `agent/agents/fsdm_metadata.py`. This is a specialized utility prompt that helps the agents understand target table schemas before the mapping begins.
*   **Discovery Tools**: All tools used by the agents are defined in `agent/tools/tools.py`. These tools provide the "hands" for the agents to interact with the SQLite database and Vector Store.

### 8.4 Agent Orchestration & Swappability
The **`AgentExecutor`** class in `agent/agents/executor.py` orchestrates the multi-phase mapping process. It manages the hand-off between the Detective (Phase 1) and the Engineer (Phase 2).

*   **Mapping Agent Swap**: The system is designed to be flexible. You can swap between two types of mapping engines in `executor.py`:
    *   **`mapping_oneshot.py` (Current Default)**: Optimized for speed and smaller models. It takes the "Discovery Intent" from the Detective and generates SQL in a single pass.
    *   **`mapping_engineer.py`**: A full ReAct agent that can autonomously query the database and explore the schema. This is recommended for larger, more capable models.
*   **How to Swap**: Both agents are compatible. To switch, simply update the import and the initialization variable in `AgentExecutor._initialize_agents()`.

---

## 9. Technical Constraints & Troubleshooting ⚠️

### 9.1 LLM Requirements
To ensure the multi-agent system functions correctly, your chosen LLM must meet these minimum requirements:
*   **Context Window**: Minimum **10,000 tokens**. The system passes detailed metadata, discovery reports, and vector context that can quickly consume smaller windows.
*   **Intelligence Level**: The model must be "smart enough" to perform multi-step SQL querying against the FSDM documentation tables.

### 9.2 Model Behavior & Failures
Smaller or less capable models (e.g., early 7B/13B parameters) often suffer from:
*   **Instruction Drift**: As the agent progresses, it may lose sight of user patterns and mandatory instructions.
*   **Tool Execution Errors**: Models may exit their loop without calling the mandatory "exit tools" (like `FSDMIntentOutput`).
*   **Symptom**: In the UI, if the **FSDM Discovery** section remains empty or the agent logs show a completion without an output report, it is likely due to the model failing to follow the structured output constraints.

### 9.3 Data Storage Persistence
All AI-generated insights, including lineage reports, SQL logic, and agent reasoning, are persisted in the project's SQLite database:
*   **File**: `projects/<project_name>/mapping.db`
*   **Table**: `final_mappings`
