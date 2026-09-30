import os
import tempfile
import streamlit as st

# Free local components (No OpenAI / No PyTorch required)
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_ollama import ChatOllama
from langchain_community.vectorstores import Chroma

# Imports with fallback support for newer LangChain versions
try:
    from langchain.chains import create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain
except ImportError:
    from langchain_classic.chains import create_retrieval_chain
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain

from langchain_core.prompts import ChatPromptTemplate

# --- STEP 1: UI Setup ---
st.set_page_config(page_title="Free Local AI Assistant", page_icon="📚", layout="wide")
st.title("📚 Local & Free AI Document Assistant")
st.subheader("Upload a PDF and ask questions — runs 100% locally on your computer!")

# File uploader widget
uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])

# Helper function to process the PDF
def process_pdf(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(file.read())
        tmp_path = tmp_file.name

    # 1. Load document pages
    loader = PyPDFLoader(tmp_path)
    docs = loader.load()

    # Preserve original filename in metadata
    for doc in docs:
        doc.metadata["source"] = file.name

    # 2. Chunk document into manageable text blocks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks = text_splitter.split_documents(docs)

    # 3. Free Local Embeddings (Runs on CPU via FastEmbed)
    embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")

    # 4. Store in Chroma Vector Store
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings
    )

    os.remove(tmp_path)
    return vector_store


# --- STEP 2: Main Application Flow ---
if uploaded_file is not None:
    if "vector_store" not in st.session_state or st.session_state.get("current_file") != uploaded_file.name:
        with st.spinner("Processing document using free local embeddings..."):
            st.session_state.vector_store = process_pdf(uploaded_file)
            st.session_state.current_file = uploaded_file.name
        st.success("Document processed successfully!")

    user_query = st.text_input("Ask a question about your document:")

    if user_query:
        with st.spinner("Generating answer with local Llama 3.2..."):
            # 1. Local Model via Ollama
            llm = ChatOllama(model="llama3.2", temperature=0)

            # 2. Retriever
            retriever = st.session_state.vector_store.as_retriever(
                search_kwargs={"k": 4}
            )

            # 3. Grounded Prompt Template
            system_prompt = (
                "You are an assistant for question-answering tasks. "
                "Use the following pieces of retrieved context to answer "
                "the question. If you don't know the answer, say that you "
                "don't know. Keep the answer concise.\n\n"
                "{context}"
            )
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
            ])

            # 4. Chains
            question_answer_chain = create_stuff_documents_chain(llm, prompt)
            rag_chain = create_retrieval_chain(retriever, question_answer_chain)

            # 5. Execute Chain
            response = rag_chain.invoke({"input": user_query})

        # --- STEP 3: Render Response & Sources ---
        st.markdown("### **Answer:**")
        st.write(response["answer"])

        st.markdown("---")
        st.markdown("### **Sources:**")
        
        sources = response.get("context", [])
        if sources:
            seen_sources = set()
            for doc in sources:
                source_name = doc.metadata.get("source", "Document")
                page_num = doc.metadata.get("page", 0) + 1
                citation = f"• **{source_name}** — Page {page_num}"
                
                if citation not in seen_sources:
                    st.markdown(citation)
                    seen_sources.add(citation)

#source venv/bin/activate
#streamlit run app.py