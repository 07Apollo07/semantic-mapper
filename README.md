# Semantic Mapper AI 🧠

**Semantic Mapper AI** is  data engineering tool that automates the mapping of source data to target data models (FSDM, ETL schemas). It utilizes a  multi-agent workflow to discover data lineage, generate transformation logic, and provide transparent technical reasoning.

---

## 📖 Documentation
For a detailed step-by-step walkthrough, technical architecture, and troubleshooting, please refer to the **[User Guide](./docs/USERGUIDE.md)**.

---

## 🚀 Key Features
...

*   **Project-Based Isolation**: Each project maintains its own isolated environment, including a vector store, metadata database, and configuration settings.
*   **Intelligent Knowledge Base**: 
    *   **Unstructured Data**: Upload PDFs and Excel reference guides to a Vector Store (ChromaDB) for semantic retrieval.
    *   **Structured Schema**: Upload target models to a local SQLite database and auto-generate AI-driven metadata for every table.
*   **Dual-Agent Orchestration**:
    *   **🕵️ The Detective (FSDM Detective)**: Traces the lineage of source fields through reference documents to understand their origin and meaning.
    *   **⚙️ The Engineer (Mapping Engineer)**: Takes the Detective's findings and generates precise SQL transformation logic and technical reasoning.
*   **Interactive Refinement**: Review AI-generated mappings, provide feedback, and regenerate specific rows to achieve  results.
*   **Golden Examples**: "Verify" generated SQL to mark it as a validated standard for your project. (to be implemented)
*   **One-Click Export**: Export your completed semantic mappings and SQL logic back to Excel.
*   **Intelligent Knowledge Base**:
    *   **Step-by-Step Transparency**: Access full discovery reports and reasoning for every generated mapping.
*   **Customizable Governance**: Define Global, FSDM Discovery, and Mapping Generation instructions to align AI behavior
---

## 🛠️ Tech Stack

*   **Frontend**: Streamlit
*   **AI Framework**: LangChain & LangGraph (ReAct Agent architecture)
*   **Database**: SQLite (Metadata, Results, Persistence)
*   **Vector Store**: ChromaDB (Semantic Retrieval)
*   **Language**: Python 3.10+

---

## 🚦 Getting Started

### 1. Installation
```bash
# Clone and enter the repo
git clone https://github.com/your-repo/semantic-mapper.git
cd semantic-mapper

# Setup environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Launch
```bash
streamlit run app.py
```

### 3. Workflow Guide
1.  **Project Initialization**: Enter a name in the "Create New Project" section to initialize your workspace or open a project.
2.  **LLM Configuration**: In the sidebar, enter your **Base URL**, click **Fetch Models**, and select your preferred LLM. Ensure you load the **Embedding Model**.
3.  **Knowledge Base Setup**:
    *   **Section 1**: Upload and **Sync** reference PDFs/Excel docs.
    *   **Section 1.2**: Upload target model Excel files, click **Create DB / Sync Tables**, and optionally **Generate Metadata** for complex tables.
4.  **Mapping Setup**: 
    *   Upload your source mapping spreadsheet in **Section 2**.
    *   Configure column headers (Source vs. Target) and click **Save & Preview**.
    *   Click **Sync Mappings to Master** to prepare the mapping queue.
5.  **Execution**: Select the target table and specific rows from the "Unified Mapping Selection" tree, then click **Generate SQL Mappings**.
6.  **Review & Export**: Inspect results in **Section 3**, use the feedback area for refinements, and export the final results to Excel.

---

## 📂 Project Structure

*   `app.py`: Main application entry point.
*   `agent/`: Agent definitions, tool logic, and orchestration (`executor.py`).
*   `logic/`: Core services for project management, data processing, and database interactions.
*   `ui/`: Modular UI components for selection trees, logs, and dashboards.
*   `projects/`: Local directory where all project data is persisted (automatically created).

---
<!-- 
## 📝 License

This project is licensed under the MIT License. -->
