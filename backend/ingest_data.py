"""
RAG Ingestion Pipeline — Solutions Architect Video Transcripts
Ingests 8 video transcript documents (TXT + DOCX) into Supabase
with proper chunking, embeddings, and metadata.

Two-Track Chunking:
  Track A: Timestamped docs (Videos 1 & 2) — split by [HH:MM:SS] markers
  Track B: Non-timestamped docs (Videos 3-9) — character/sentence split
"""

import os
import re
import sys
import logging
import time
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_openai import OpenAIEmbeddings

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

# Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path, override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

# ============================================================
# DOCS DIRECTORY
# ============================================================
DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs')

# ============================================================
# VIDEO METADATA — All 8 videos
# ============================================================

VIDEO_METADATA = [
    {
        "filename": f"sc video {i}.docx",
        "filetype": "docx",
        "has_timestamps": False,
        "source_type": "transcript",
        "title": f"SC Video {i} Transcript",
        "author_or_channel": "Unknown",
        "url_or_identifier": f"sc-video-{i}",
        "global_summary": f"Transcript for SC Video {i}",
    }
    for i in range(1, 9)
]


# ============================================================
# PARSING FUNCTIONS
# ============================================================

def read_txt_file(filepath: str) -> str:
    """Read a plain text file and return its content."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def read_docx_file(filepath: str) -> str:
    """Read a DOCX file and return combined paragraph text."""
    import docx
    doc = docx.Document(filepath)
    return "\n".join(p.text for p in doc.paragraphs)


def extract_transcript_text(raw_text: str, has_timestamps: bool) -> str:
    """
    Extract just the transcript portion from the raw file text.
    Strips header lines (Video Name, Link, TITLE, VIDEO URL, separator lines).
    """
    lines = raw_text.split('\n')
    transcript_lines = []
    header_done = False

    for line in lines:
        stripped = line.strip()
        # Skip empty lines at the top
        if not header_done:
            # Skip known header patterns
            if (stripped.lower().startswith('video name:') or
                stripped.lower().startswith('title:') or
                stripped.lower().startswith('video url:') or
                stripped.lower().startswith('link:') or
                stripped.lower().startswith('transcript:') or
                stripped.startswith('====') or
                stripped == ''):
                continue
            else:
                header_done = True

        if header_done and stripped:
            transcript_lines.append(stripped)

    return "\n".join(transcript_lines)


# ============================================================
# CHUNKING FUNCTIONS
# ============================================================

def chunk_timestamped(transcript_text: str, chunk_size: int = 800) -> list:
    """
    Track A: For timestamped docs.
    Split by [HH:MM:SS] markers, then group segments into ~chunk_size char chunks.
    Returns list of dicts: {"content": str, "location_marker": str}
    """
    # Split by timestamp pattern
    ts_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2})\]\s*')
    parts = ts_pattern.split(transcript_text)

    # parts alternates: [text_before_first_ts, ts1, text1, ts2, text2, ...]
    segments = []
    i = 0
    # Skip any text before the first timestamp
    if parts and not re.match(r'\d{2}:\d{2}:\d{2}', parts[0]):
        i = 1

    while i < len(parts) - 1:
        timestamp = parts[i]
        text = parts[i + 1].strip()
        if text:
            segments.append({"timestamp": timestamp, "text": text})
        i += 2

    if not segments:
        # Fallback: treat entire text as one chunk
        return [{"content": transcript_text.strip(), "location_marker": "00:00:00"}]

    # Group segments into chunks of ~chunk_size characters
    chunks = []
    current_text = ""
    current_ts = segments[0]["timestamp"]

    for seg in segments:
        if len(current_text) + len(seg["text"]) > chunk_size and current_text:
            chunks.append({
                "content": current_text.strip(),
                "location_marker": current_ts
            })
            current_text = seg["text"]
            current_ts = seg["timestamp"]
        else:
            current_text += " " + seg["text"] if current_text else seg["text"]

    # Don't forget the last chunk
    if current_text.strip():
        chunks.append({
            "content": current_text.strip(),
            "location_marker": current_ts
        })

    return chunks


def chunk_by_characters(transcript_text: str, chunk_size: int = 800, overlap: int = 100) -> list:
    """
    Track B: For non-timestamped docs (speech-to-text with no punctuation).
    Character-based chunking that splits at word boundaries with overlap.
    Returns list of dicts: {"content": str, "location_marker": str}
    """
    text = transcript_text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    segment_num = 1

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            # Last chunk - take everything remaining
            chunk_text = text[start:].strip()
            if chunk_text and len(chunk_text) >= 30:
                chunks.append({
                    "content": chunk_text,
                    "location_marker": f"Segment {segment_num}"
                })
            break

        # Try to break at a word boundary (space) near the end
        break_point = text.rfind(' ', start + chunk_size // 2, end)
        if break_point > start:
            end = break_point

        chunk_text = text[start:end].strip()
        if chunk_text and len(chunk_text) >= 30:
            chunks.append({
                "content": chunk_text,
                "location_marker": f"Segment {segment_num}"
            })
            segment_num += 1

        # Move start forward, with some overlap for context
        start = end - overlap

    return chunks


# ============================================================
# INGESTION FUNCTION
# ============================================================

def ingest_video_transcript(video_meta: dict) -> dict:
    """
    Ingests a single video transcript into Supabase.
    1. Read file (TXT or DOCX)
    2. Extract transcript text
    3. Chunk using appropriate strategy
    4. Create parent source in knowledge_sources
    5. Generate embeddings and insert chunks into knowledge_chunks
    """
    filepath = os.path.join(DOCS_DIR, video_meta["filename"])
    logger.info(f"Ingesting: {video_meta['title']}")
    logger.info(f"  File: {video_meta['filename']}")

    # Step 1: Read file
    if video_meta["filetype"] == "txt":
        raw_text = read_txt_file(filepath)
    else:
        raw_text = read_docx_file(filepath)

    # Step 2: Extract transcript
    transcript = extract_transcript_text(raw_text, video_meta["has_timestamps"])
    logger.info(f"  Transcript length: {len(transcript)} chars")

    # Step 3: Chunk
    if video_meta["has_timestamps"]:
        chunks = chunk_timestamped(transcript)
        logger.info(f"  Chunking: TIMESTAMP-BASED -> {len(chunks)} chunks")
    else:
        chunks = chunk_by_characters(transcript)
        logger.info(f"  Chunking: CHARACTER-BASED -> {len(chunks)} chunks")

    # Step 4: Create parent source
    source_res = supabase.table("knowledge_sources").insert({
        "source_type": video_meta["source_type"],
        "title": video_meta["title"],
        "author_or_channel": video_meta["author_or_channel"],
        "url_or_identifier": video_meta["url_or_identifier"],
        "global_summary": video_meta["global_summary"],
    }).execute()

    if not source_res.data:
        raise Exception(f"Failed to create knowledge source for: {video_meta['title']}")

    source_id = source_res.data[0]['id']
    logger.info(f"  Parent source created: {source_id}")

    # Step 5: Generate embeddings and insert chunks
    chunk_data = []
    for idx, chunk in enumerate(chunks):
        content = chunk["content"]
        if len(content.strip()) < 30:  # Skip tiny fragments
            continue

        logger.info(f"  Embedding chunk {idx + 1}/{len(chunks)} ({len(content)} chars)...")
        vector = embeddings_model.embed_query(content)

        chunk_data.append({
            "source_id": source_id,
            "chunk_index": idx,
            "content": content,
            "location_marker": chunk["location_marker"],
            "embedding": vector,
        })

        # Small delay to avoid rate limits
        if (idx + 1) % 10 == 0:
            time.sleep(0.5)

    # Batch insert (groups of 20 to avoid payload limits)
    batch_size = 20
    for i in range(0, len(chunk_data), batch_size):
        batch = chunk_data[i:i + batch_size]
        supabase.table("knowledge_chunks").insert(batch).execute()
        logger.info(f"  Batch {i // batch_size + 1}: Inserted {len(batch)} chunks")

    logger.info(f"  DONE: {len(chunk_data)} chunks inserted for: {video_meta['title']}")
    return {"source_id": source_id, "chunks_inserted": len(chunk_data)}


# ============================================================
# PDF BOOK INGESTION FUNCTION
# ============================================================

BOOK_METADATA = {
    "source_type": "book",
    "title": "Mastering Technical Sales: The Sales Engineer's Handbook (4th Edition)",
    "author_or_channel": "John Care",
    "url_or_identifier": "mastering_technical_sales_john_care_4e_pdf",
    "global_summary": (
        "The definitive handbook for Sales Engineers and technical pre-sales professionals. "
        "Covers the full SE lifecycle including discovery, demos, POC management, RFP responses, "
        "working with sales reps, competitive positioning, presenting to C-suite executives, "
        "building business cases, and career development for technical sales roles."
    ),
}

BOOK_PDF_PATH = os.path.join(
    DOCS_DIR,
    'Mastering Technical Sales The Sales Engineers Handbook (John Care) (z-library.sk, 1lib.sk, z-lib.sk).pdf'
)


def ingest_pdf_book(pdf_path: str, metadata: dict, chunk_size: int = 800, chunk_overlap: int = 200) -> dict:
    """
    Ingests a PDF book into Supabase.
    Extracts text page-by-page, applies recursive chunking, and embeds.
    """
    import fitz  # PyMuPDF

    logger.info(f"Ingesting PDF book: {metadata['title']}")
    logger.info(f"  Path: {pdf_path}")

    # 1. Extract text from PDF
    doc = fitz.open(pdf_path)
    pages_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if text:  # Skip empty pages
            pages_text.append({
                "page": page_num + 1,
                "text": text
            })
    doc.close()
    logger.info(f"  Extracted text from {len(pages_text)} non-empty pages")

    # 2. Create Parent Source
    source_res = supabase.table("knowledge_sources").insert({
        "source_type": metadata["source_type"],
        "title": metadata["title"],
        "author_or_channel": metadata["author_or_channel"],
        "url_or_identifier": metadata["url_or_identifier"],
        "global_summary": metadata["global_summary"]
    }).execute()

    if not source_res.data:
        raise Exception(f"Failed to create knowledge source for: {metadata['title']}")

    source_id = source_res.data[0]['id']
    logger.info(f"  Parent source created: {source_id}")

    # 3. Chunk pages with overlap
    chunk_data = []
    chunk_idx = 0

    for page_info in pages_text:
        page_text = page_info["text"]
        page_num = page_info["page"]

        # If page text is short enough, treat as single chunk
        if len(page_text) <= chunk_size:
            chunks = [page_text]
        else:
            # Recursive split at paragraph boundaries
            chunks = []
            start = 0
            while start < len(page_text):
                end = start + chunk_size
                if end < len(page_text):
                    last_break = page_text.rfind('\n', start, end)
                    if last_break > start + chunk_size // 2:
                        end = last_break + 1
                chunk_text = page_text[start:end].strip()
                if chunk_text:
                    chunks.append(chunk_text)
                start = end - chunk_overlap if end < len(page_text) else end

        for chunk_text in chunks:
            if len(chunk_text.strip()) < 30:  # Skip tiny fragments
                continue

            logger.info(f"  Embedding chunk {chunk_idx + 1}: Page {page_num} ({len(chunk_text)} chars)")
            vector = embeddings_model.embed_query(chunk_text)

            chunk_data.append({
                "source_id": source_id,
                "chunk_index": chunk_idx,
                "content": chunk_text,
                "location_marker": f"Page {page_num}",
                "embedding": vector
            })
            chunk_idx += 1

            if chunk_idx % 20 == 0:
                time.sleep(1)

    # 4. Batch insert (in groups of 20 to avoid payload limits)
    batch_size = 20
    for i in range(0, len(chunk_data), batch_size):
        batch = chunk_data[i:i + batch_size]
        supabase.table("knowledge_chunks").insert(batch).execute()
        logger.info(f"  Batch {i // batch_size + 1}: Inserted {len(batch)} chunks")

    logger.info(f"  TOTAL: {len(chunk_data)} chunks inserted for: {metadata['title']}")
    return {"source_id": source_id, "chunks_inserted": len(chunk_data)}


# ============================================================
# MAIN — Run the full ingestion
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("STARTING FULL RAG INGESTION PIPELINE")
    logger.info("Domain: Enterprise Pre-Sales & Solutions Architecture")
    logger.info("=" * 60)

    results = []

    # --- Ingest Video Transcripts ---
    for i, video in enumerate(VIDEO_METADATA):
        logger.info(f"\n--- Video {i + 1}/{len(VIDEO_METADATA)} ---")
        try:
            result = ingest_video_transcript(video)
            results.append((video["title"], result))
        except Exception as e:
            logger.error(f"FAILED: {video['title']} -> {e}")

    # --- Ingest PDF Book ---
    logger.info(f"\n--- PDF Book ---")
    try:
        r_book = ingest_pdf_book(BOOK_PDF_PATH, BOOK_METADATA)
        results.append((BOOK_METADATA["title"], r_book))
    except Exception as e:
        logger.error(f"FAILED: Book ingestion -> {e}")

    # --- Summary ---
    logger.info("\n" + "=" * 60)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 60)
    total_chunks = 0
    for name, result in results:
        logger.info(f"  OK: {name}: {result['chunks_inserted']} chunks (source: {result['source_id']})")
        total_chunks += result['chunks_inserted']
    logger.info(f"\nTotal: {len(results)} sources, {total_chunks} chunks")
    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE -- Knowledge Hub is ready.")

