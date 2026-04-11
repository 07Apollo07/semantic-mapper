import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

def generate_metadata(sample_df, model_name, api_key, base_url):
    """
    Generates a descriptive metadata string for an FSDM sheet based on sample data.
    """
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )
    # llm = ChatOpenAI(
    #     model=model_name,
    #     api_key=api_key,
    #     base_url=base_url
    # )
    
    prompt = ChatPromptTemplate.from_template(
        "Analyze the following sample data from a database table:\n\n{sample_data}\n\n"
        "Provide a concise text description of the table's purpose and define the role of its columns. "
        "This description will be used as instructions for an AI agent performing data mapping. "
        "Focus on clarity and technical accuracy."
    )
    
    response = llm.invoke(prompt.format(sample_data=sample_df))
    return response.content
