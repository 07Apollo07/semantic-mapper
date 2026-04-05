# Project Reflection: Semantic Mapper AI

## 1. Project Overview
**Semantic Mapper AI** is a specialized tool designed to automate the complex process of data mapping, particularly for ETL (Extract, Transform, Load) and FSDM (Financial Services Data Model) projects. Its primary goal is to take a source data field and a target data field, and using AI, generate the necessary transformation logic (typically SQL) to bridge them.

It leverages a "Human-in-the-loop" approach, where an AI agent proposes mappings and a human user reviews, provides feedback, and refines them.

---

## 2. Technical Stack
- **Frontend/UI:** Streamlit (v1.x) - providing a responsive, dashboard-like experience.
- **Orchestration:** LangChain & LangGraph - used for building the ReAct agent and managing complex state transitions.
- **Vector Store:** ChromaDB - handles unstructured documentation (PDFs, Excel metadata) for RAG (Retrieval-Augmented Generation).
- **Structured Storage:** SQLite - stores project metadata, FSDM models, and the "Source of Truth" mapping records.
- **Embeddings:** HuggingFace (`Snowflake/snowflake-arctic-embed-s`) - local embeddings for privacy and performance.
- **LLM Integration:** Flexible support for OpenAI (GPT-4o) and local models (via Ollama/Base URL configuration).
- **Data Handling:** Pandas & OpenPyXL - for processing Excel-based mapping sheets and documentation.

---

## 3. Current Key Features & Functionality

### 📂 Multi-Project Management
- Isolated project environments with persistent state stored in `projects/<project_name>/`.

### 🧠 Knowledge Base Manager (RAG)
- **Unstructured Data:** PDF/Excel indexing into ChromaDB.
- **Structured Data (FSDM/ETL):** Excel models converted to queryable SQLite tables for "Text-to-SQL" context retrieval.

### 🤖 ReAct Agent Architecture
- Employs `vector_tool`, `fsdm_tool`, and `mapping_tool` to gather multi-dimensional context before generating SQL logic and reasoning.

---

## 4. Proposed Architectural Evolution (Roadmap)

The project is transitioning from a stateless "Row-by-Row" range processor to a **Stateful, Table-Centric Mapping Engine**.

### 🏗️ 1. Table-Centric Execution & Global Context
- **Shift from Range to Entity:** Instead of processing "Rows 1-50", the user selects a **Target Table** from a dropdown. The system automatically identifies all associated rows in the mapping document.
- **Global Instruction Hub:** A dedicated interface for users to provide "Project-Wide Instructions" (e.g., standard null handling, date formats). These are injected into every agent prompt for consistency.

### 🔍 2. The "Pre-mapping Insight" Phase (Preprocessing)
Before a single line of SQL is written, the system enters an "Insight Generation" step for every row:
- **Deep Context Retrieval:** The system pulls descriptions for the Source Column (from Vector Store), Source Table (from FSDM SQLite), and Target Table (from documentation).
- **Intent Generation:** The AI generates a "Technical Hypothesis"—a natural language description of what the column represents, its lineage, and its intended transformation path.
- **Human Verification Gate:** This insight is displayed to the user with a regenerate button and a correction text box. **Execution is paused until a human validates the intent.** This ensures the agent is on the "right track" before generating complex code.

### 🗄️ 3. SQLite as the Absolute Source of Truth
Moving away from ephemeral session state and JSON metadata:
- **Persistent Mapping DB:** A dedicated SQLite table (`final_mappings`) will store the entire lifecycle of every mapping row:
    - Metadata (Source/Target info)
    - AI-generated Pre-mapping Insight
    - Human-provided Corrections
    - Validation Status (Pending/Verified)
    - Final SQL Logic
- **Pattern Recall:** The agent will query this DB for previously verified patterns to ensure project-wide consistency.

### 📜 4. Comprehensive Logging & Audit
- **Total Visibility:** Logs will capture every step: Extraction -> Context Discovery -> Preprocessing -> Human Approval -> Agent Invocation -> Final SQL Generation.
- **Audit Trail:** Maintain a permanent project log that tracks each step and user interaction for complete transparency.

---

## 5. Personal View & Conclusion
The proposed shift to a **Target-Table Centric** approach with a **Mandatory Preprocessing Gate** transforms the Semantic Mapper AI from a productivity tool into a robust data engineering platform. By forcing a "Human-in-the-loop" check on the *intent* before the *implementation*, we drastically reduce the "hallucination loop" and ensure high-fidelity results that data architects can trust.
