"""Build and load the Chroma vector store used for retrieval-augmented analysis."""
import shutil

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import config
from app.llm import get_embeddings
from app.models.schemas import ParsedDocument

COLLECTION_NAME = "financial_documents"


def documents_to_chunks(parsed_docs: list[ParsedDocument]) -> list[Document]:
    """Split every section of every parsed document into embeddable chunks,
    carrying metadata needed for filtered retrieval (company, period, section type)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    chunks: list[Document] = []
    for doc in parsed_docs:
        for section in doc.sections:
            for i, chunk_text in enumerate(splitter.split_text(section.content)):
                chunks.append(
                    Document(
                        page_content=chunk_text,
                        metadata={
                            "company": doc.company,
                            "ticker": doc.ticker,
                            "period_label": doc.period_label,
                            "fiscal_year": doc.fiscal_year,
                            "doc_type": doc.doc_type,
                            "section_type": section.section_type,
                            "section_title": section.title,
                            "source_path": doc.source_path,
                            "chunk_index": i,
                        },
                    )
                )
    return chunks


def build_vectorstore(
    parsed_docs: list[ParsedDocument],
    persist_dir: str | None = None,
    reset: bool = True,
) -> Chroma:
    """Embed all document chunks and persist them to a Chroma collection."""
    persist_dir = persist_dir or config.CHROMA_PERSIST_DIR
    if reset:
        shutil.rmtree(persist_dir, ignore_errors=True)

    chunks = documents_to_chunks(parsed_docs)
    return Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name=COLLECTION_NAME,
        persist_directory=persist_dir,
    )


def get_vectorstore(persist_dir: str | None = None) -> Chroma:
    """Load an already-persisted Chroma collection."""
    persist_dir = persist_dir or config.CHROMA_PERSIST_DIR
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=persist_dir,
    )