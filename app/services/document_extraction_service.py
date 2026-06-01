"""Extract text from PDF and DOCX files, then chunk for RAG embedding."""
import re
from pathlib import Path

MAX_CHUNK_CHARS = 800
OVERLAP_CHARS = 100


def extract_text_from_pdf(file_path: "str | Path") -> list[str]:
    """
    Extract text from a PDF file, one string per page.
    Returns list of non-empty page strings.
    """
    from pypdf import PdfReader
    reader = PdfReader(str(file_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append(text)
    return pages


def extract_text_from_docx(file_path: "str | Path") -> list[str]:
    """
    Extract text from a DOCX file, one string per paragraph section.
    Groups paragraphs under the same heading into one chunk.
    Returns list of non-empty section strings.
    """
    import docx
    doc = docx.Document(str(file_path))
    sections: list[str] = []
    current: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        # Start a new section on headings
        if para.style.name.startswith("Heading"):
            if current:
                sections.append("\n".join(current))
            current = [text]
        else:
            current.append(text)
    if current:
        sections.append("\n".join(current))
    return sections


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """
    Split a long text into overlapping chunks of at most max_chars characters.
    If text is already short enough, returns [text].
    """
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def extract_chunks(file_path: "str | Path", file_type: str) -> list[str]:
    """
    Main entry point: extract text from file and return flat list of chunks.
    file_type: "pdf" | "docx" | "txt"
    """
    path = Path(file_path)
    if file_type == "pdf":
        sections = extract_text_from_pdf(path)
    elif file_type == "docx":
        sections = extract_text_from_docx(path)
    elif file_type == "txt":
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
        sections = [raw] if raw else []
    else:
        return []

    chunks: list[str] = []
    for section in sections:
        chunks.extend(chunk_text(section))
    # Filter out chunks that are too short to be useful
    return [c for c in chunks if len(c.strip()) >= 30]
