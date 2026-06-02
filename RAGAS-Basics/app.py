import streamlit as st

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM

st.set_page_config(
    page_title="IT Support Assistant",
    layout="wide"
)

st.title("IT Support Assistant")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

db = Chroma(
    persist_directory="vectorstore",
    embedding_function=embeddings
)

llm = OllamaLLM(
    model="llama3.1:8b"
)

question = st.text_input(
    "Ask a question"
)

if question:

    docs = db.similarity_search(
        question,
        k=3
    )

    context = "\n".join(
        [doc.page_content for doc in docs]
    )

    prompt = f"""
    Use only the provided context.

    Context:
    {context}

    Question:
    {question}
    """

    response = llm.invoke(prompt)

    st.subheader("Answer")
    st.write(response)
