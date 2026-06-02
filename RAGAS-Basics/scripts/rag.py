from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM

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

question = input("Question: ")

docs = db.similarity_search(question, k=3)

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

print("\nAnswer:\n")
print(response)
