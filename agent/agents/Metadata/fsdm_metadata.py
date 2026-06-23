import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

def generate_metadata(sample_df, model_name, api_key, base_url):
    """
    Generates a descriptive metadata string for an FSDM sheet based on sample data.
    """
    llm = ChatOpenAI(
        model=model_name,
        # temperature=0.,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )
    # llm = ChatOpenAI(
    #     model=model_name,
    #     api_key=api_key,
    #     base_url=base_url
    # )
    
    prompt = ChatPromptTemplate.from_template(
        "Analyze the provided sample data (which contains ONLY 5 rows of data) from the database table."
        "Strictly follow these instructions to generate metadata for this table:\n\n"
        "{sample_data}\n\n"
        "1. Your ONLY task is to provide a dictionary-like metadata definition for each headers.\n"
        "2. Do NOT mention any data, values, or content from the rows. This input is only 5 rows of sample data; do not infer anything from the actual data values.\n"
        "3. Focus solely on defining the purpose and role of each header based on its name from Headers:\n"
        "4. Output format must be: \"Header name\": Definition.\n"
        "5. Do NOT rename header names, do not use quotes/brackets around them, and do not modify them in any way. Keep them exactly as provided.\n"
        "6. Keep definitions simple, concise, and clear.\n"
    )
    
    response = llm.invoke(prompt.format(sample_data=sample_df))
    return response.content
