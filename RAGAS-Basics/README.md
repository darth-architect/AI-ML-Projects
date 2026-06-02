# RAGAS Basics - Local RAG Foundation

## Overview

This project demonstrates a Retrieval-Augmented Generation (RAG) system running completely locally.

The solution uses:

- Ollama for LLM inference
- ChromaDB as Vector Database
- Sentence Transformers for embeddings
- LangChain for orchestration
- Streamlit for UI

---

## Architecture

User Question
    ↓
Retriever
    ↓
ChromaDB
    ↓
Relevant Context
    ↓
Ollama
    ↓
Generated Response

---

## Learning Objectives

- Understand embeddings
- Understand vector databases
- Build a local RAG pipeline
- Learn semantic search
- Prepare for RAGAS evaluation

---

## Project Components

### ingest.py

Loads documents, chunks content, generates embeddings and stores them in ChromaDB.

### rag.py

Performs retrieval and sends context to the LLM.

### app.py

Provides a Streamlit-based chat interface.

---

## Future Enhancements

- Conversation history
- Source citations
- RAGAS evaluation
- Dashboarding
- ServiceNow KB integration
