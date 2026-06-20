"""Document chunking utilities for the RAG pipeline."""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import config
from app.models.schemas import ParsedDocument


def documents_to_chunks(parsed_docs: list[ParsedDocument]) -> list[Document]:
    """Split every section of every parsed document into chunks for retrieval."""
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
