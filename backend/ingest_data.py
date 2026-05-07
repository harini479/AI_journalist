"""
RAG Ingestion Pipeline — Transcripts + Books
Ingests interview transcripts and PDF books into Supabase
with proper chunking, embeddings, and metadata.
"""

import os
import re
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_openai import OpenAIEmbeddings

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
# TRANSCRIPT DATA (Pre-loaded from your provided content)
# ============================================================

TRANSCRIPT_1 = {
    "metadata": {
        "source_type": "transcript",
        "title": "Parenting Styles — Authoritative vs Authoritarian vs Permissive",
        "author_or_channel": "Meghna & Devi Shobha",
        "url_or_identifier": "parenting_styles_interview_01",
        "global_summary": "Deep dive into the four research-backed parenting styles (Authoritarian, Authoritative, Permissive, Uninvolved), the EAR method for becoming an authoritative parent, and strategies for navigating parenting style clashes between partners."
    },
    "sections": [
        {
            "timestamp": "00:00:01",
            "title": "Introduction to Parenting Styles",
            "content": "The hosts, Meghna and Devi Shobha, introduce the concept of parenting styles. The way parents interact with and discipline their children can have profound, long-lasting effects on their development and future behavior."
        },
        {
            "timestamp": "00:02:40",
            "title": "Definition of Parenting Styles",
            "content": "Parenting styles are defined as consistent traits that encompass a parent's overall attitude, body language, tone, and quality of attention toward raising a child."
        },
        {
            "timestamp": "00:05:03",
            "title": "Two Key Personality Attributes",
            "content": "Researchers categorize these styles based on two main personality attributes: Responsiveness (Warmth) — How well a parent meets their child's emotional needs. Demandingness (Control) — The extent to which parents expect children to meet behavioral expectations and follow rules."
        },
        {
            "timestamp": "00:08:19",
            "title": "Authoritarian Parenting",
            "content": "Authoritarian Parenting: This style features high demandingness and low warmth. It is the 'because I said so' approach with strict rules and zero tolerance for questions. While children may appear compliant under the parent's gaze, they often become defiant, reclusive, or prone to substance abuse later in life."
        },
        {
            "timestamp": "00:10:20",
            "title": "Authoritative Parenting — The Ideal Style",
            "content": "Authoritative Parenting (The Ideal Style): This style balances high demandingness with high warmth. Parents set firm, consistent limits but are responsive and attentive to their child's needs. They explain the reasoning behind rules, fostering mutual respect, critical thinking, and emotional regulation."
        },
        {
            "timestamp": "00:13:03",
            "title": "Permissive Parenting",
            "content": "Permissive Parenting: Highly warm but with very low demandingness. These parents adopt a 'kids will be kids' mindset and avoid enforcing rules or discipline. Children often end up impulsive, struggle with limits, and face difficulties adjusting to authority in the real world."
        },
        {
            "timestamp": "00:16:07",
            "title": "Uninvolved (Neglectful) Parenting",
            "content": "Uninvolved (Neglectful) Parenting: Featuring both low warmth and low demandingness. Parents offer no guidance, rules, or emotional connection, often leaving children to figure things out alone. This style is sometimes linked to a parent's mental illness, chronic illness, or substance abuse."
        },
        {
            "timestamp": "00:20:18",
            "title": "The EAR Method Introduction",
            "content": "Shobha introduces the acronym 'EAR' as a framework to help parents tweak their approach to become more authoritative. EAR stands for Emotional Regulation, Autonomy, and Rules & Consistency."
        },
        {
            "timestamp": "00:21:32",
            "title": "E — Emotional Regulation",
            "content": "Emotional Regulation: It starts with validating your child's feelings rather than trivializing them (e.g., saying 'stop crying' or 'it's no big deal'). Helping children recognize and name their triggers teaches them to choose healthy responses rather than just suppressing their emotions."
        },
        {
            "timestamp": "00:26:07",
            "title": "A — Autonomy",
            "content": "Autonomy: Hold kids to high standards but set them up for success. Instead of bailing children out (like driving them to school when they dawdle), allow them to experience natural consequences. Support them with tools (like checklists) so they can learn to complete tasks independently."
        },
        {
            "timestamp": "00:31:42",
            "title": "R — Rules & Consistency",
            "content": "Rules & Consistency: Be consistent with your rules and limits. If you set a rule or a timer, stick to it. Without consistency, children learn that limits are just empty threats."
        },
        {
            "timestamp": "00:33:36",
            "title": "Navigating Parenting Clashes with Partner",
            "content": "It is incredibly common for partners to have mismatched parenting styles (e.g., one is authoritarian while the other is permissive)."
        },
        {
            "timestamp": "00:36:29",
            "title": "Divide and Rule Strategy",
            "content": "Shobha and Meghna recommend a 'divide and rule' strategy to minimize stepping on each other's toes. Assign specific duties (like feeding or bath time) to one parent."
        },
        {
            "timestamp": "00:37:34",
            "title": "United Front & Non-Verbal Signals",
            "content": "Always present a united front to your children. Discuss any disagreements in private, outside the purview of the kids. Establish a non-verbal signal with your partner. If one parent is getting dysregulated or frustrated with the child, the other can subtly signal to swap in, allowing the frustrated parent to take a breather without undermining their authority."
        },
        {
            "timestamp": "00:40:12",
            "title": "Conclusion",
            "content": "Parenting is not black and white, and shifting towards an authoritative style is a gradual, daily journey."
        }
    ]
}

TRANSCRIPT_2 = {
    "metadata": {
        "source_type": "transcript",
        "title": "Sleep Training — Building Independent Sleep Habits for Infants",
        "author_or_channel": "Ajitha Gopal Sitapadli (Sleep Right Program)",
        "url_or_identifier": "sleep_training_interview_02",
        "global_summary": "Comprehensive discussion on infant sleep training covering what sleep training actually is, avoiding external crutches, when to start, prioritizing maternal well-being, co-sleeping considerations, and the long-term benefits of healthy sleep habits for brain development and growth."
    },
    "sections": [
        {
            "timestamp": "00:00:00",
            "title": "Introduction to Sleep Training",
            "content": "The hosts introduce the challenges of infant sleep and the toll sleep deprivation takes on parental well-being, highlighting that poor sleep can contribute to depression and poor health in mothers."
        },
        {
            "timestamp": "00:02:01",
            "title": "Meet the Guest — Ajitha Gopal Sitapadli",
            "content": "Ajitha Gopal Sitapadli, who formulated the 'Sleep Right' program, shares how her own struggles with her firstborn's sleep deprivation drove her to find actionable, research-backed solutions."
        },
        {
            "timestamp": "00:02:52",
            "title": "What is Sleep Training?",
            "content": "Ajitha reframes sleep training — noting it often gets a bad reputation — as simply teaching babies healthy sleep habits so they can learn to sleep independently for longer durations."
        },
        {
            "timestamp": "00:04:30",
            "title": "Avoiding External Crutches",
            "content": "A core component of independent sleep is avoiding 'external crutches,' which are associations out of the child's control (like needing to be held, rocked, or fed to fall asleep). Conversely, self-soothing behaviors like thumb-sucking are considered healthy because the child controls them."
        },
        {
            "timestamp": "00:05:45",
            "title": "When to Start Sleep Training",
            "content": "While the active elimination of sleep crutches typically starts after five months of age, Ajitha emphasizes that parents can begin laying the groundwork for healthy sleep habits from the day they bring their baby home."
        },
        {
            "timestamp": "00:08:09",
            "title": "The Difference Between Needs and Crutches",
            "content": "The discussion clarifies that while feeding is a primary need, indiscriminately using it to put a baby to sleep sets up a reliance. If you always feed a child to sleep, you are teaching them that suckling is the required pathway to rest."
        },
        {
            "timestamp": "00:11:12",
            "title": "Past vs. Present Parenting Dynamics",
            "content": "Ajitha contrasts previous generations with today's parents. In the past, larger support systems (like joint families) allowed mothers to rest more, whereas modern parents are often spread thin balancing careers, families, and social lives, pushing themselves to the point of extreme exhaustion."
        },
        {
            "timestamp": "00:17:27",
            "title": "Prioritizing the Mother's Well-being",
            "content": "Sleep training requires focused effort and consistency. If a mother is severely sleep-deprived or dealing with anxiety and depression, her health must be prioritized first. Ajitha likens the mother to the root of a tree — if the root is unhealthy, the rest of the tree cannot flourish."
        },
        {
            "timestamp": "00:20:44",
            "title": "Basic Steps for Healthy Sleep",
            "content": "Calm Environments: Create a predictable, relaxing bedtime routine. Age-Appropriate Awake Windows: Ensure babies aren't kept awake too long. Keeping an overtired child awake in hopes they will sleep longer is a myth; an overtired child actually has a much harder time falling and staying asleep."
        },
        {
            "timestamp": "00:28:05",
            "title": "Long-Term Benefits of Good Sleep",
            "content": "Sleep is compared to a 'master button' for health. Good sleep is essential for infant brain development, physical growth, and emotional regulation. Conversely, studies have shown that poor early sleep patterns can be a predictive factor for issues like childhood obesity and behavioral problems later in life."
        },
        {
            "timestamp": "00:35:18",
            "title": "Is Co-Sleeping Okay?",
            "content": "A host asks if lying down with children until they fall asleep is a bad habit. Ajitha confirms that if the setup results in uninterrupted, quality sleep for both the parent and the child without causing stress, there is no need to change what is working."
        }
    ]
}

# ============================================================
# INGESTION FUNCTIONS
# ============================================================

def ingest_transcript(transcript_data: dict) -> dict:
    """
    Ingests a structured transcript into Supabase.
    Each timestamped section becomes its own chunk with the timestamp as location_marker.
    """
    meta = transcript_data["metadata"]
    sections = transcript_data["sections"]

    logger.info(f"📥 Ingesting transcript: {meta['title']}")

    # 1. Create Parent Source
    source_res = supabase.table("knowledge_sources").insert({
        "source_type": meta["source_type"],
        "title": meta["title"],
        "author_or_channel": meta["author_or_channel"],
        "url_or_identifier": meta["url_or_identifier"],
        "global_summary": meta["global_summary"]
    }).execute()

    if not source_res.data:
        raise Exception(f"Failed to create knowledge source for: {meta['title']}")

    source_id = source_res.data[0]['id']
    logger.info(f"  ✅ Parent source created: {source_id}")

    # 2. Build chunks from sections
    chunk_data = []
    for idx, section in enumerate(sections):
        # Combine title + content for richer semantic embedding
        full_content = f"[{section['title']}] {section['content']}"

        logger.info(f"  🔗 Embedding chunk {idx + 1}/{len(sections)}: {section['title'][:50]}...")
        vector = embeddings_model.embed_query(full_content)

        chunk_data.append({
            "source_id": source_id,
            "chunk_index": idx,
            "content": full_content,
            "location_marker": section["timestamp"],
            "embedding": vector
        })

    # 3. Batch insert chunks
    supabase.table("knowledge_chunks").insert(chunk_data).execute()
    logger.info(f"  ✅ Inserted {len(chunk_data)} chunks for: {meta['title']}")

    return {"source_id": source_id, "chunks_inserted": len(chunk_data)}


def ingest_pdf_book(pdf_path: str, metadata: dict, chunk_size: int = 800, chunk_overlap: int = 200) -> dict:
    """
    Ingests a PDF book into Supabase.
    Extracts text page-by-page, applies recursive chunking, and embeds.
    """
    import fitz  # PyMuPDF

    logger.info(f"📥 Ingesting PDF book: {metadata['title']}")
    logger.info(f"  📄 Path: {pdf_path}")

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
    logger.info(f"  📄 Extracted text from {len(pages_text)} non-empty pages")

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
    logger.info(f"  ✅ Parent source created: {source_id}")

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
                # Try to break at paragraph boundary
                if end < len(page_text):
                    # Look for last newline before end
                    last_break = page_text.rfind('\n', start, end)
                    if last_break > start + chunk_size // 2:  # Only if break is in second half
                        end = last_break + 1
                chunk_text = page_text[start:end].strip()
                if chunk_text:
                    chunks.append(chunk_text)
                start = end - chunk_overlap if end < len(page_text) else end

        for chunk_text in chunks:
            if len(chunk_text.strip()) < 30:  # Skip tiny fragments
                continue

            logger.info(f"  🔗 Embedding chunk {chunk_idx + 1}: Page {page_num} ({len(chunk_text)} chars)")
            vector = embeddings_model.embed_query(chunk_text)

            chunk_data.append({
                "source_id": source_id,
                "chunk_index": chunk_idx,
                "content": chunk_text,
                "location_marker": f"Page {page_num}",
                "embedding": vector
            })
            chunk_idx += 1

    # 4. Batch insert (in groups of 20 to avoid payload limits)
    batch_size = 20
    for i in range(0, len(chunk_data), batch_size):
        batch = chunk_data[i:i + batch_size]
        supabase.table("knowledge_chunks").insert(batch).execute()
        logger.info(f"  📦 Batch {i // batch_size + 1}: Inserted {len(batch)} chunks")

    logger.info(f"  ✅ Total: {len(chunk_data)} chunks inserted for: {metadata['title']}")
    return {"source_id": source_id, "chunks_inserted": len(chunk_data)}


# ============================================================
# MAIN — Run the full ingestion
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 STARTING FULL RAG INGESTION PIPELINE")
    logger.info("=" * 60)

    results = []

    # --- Ingest Transcript 1: Parenting Styles ---
    try:
        r1 = ingest_transcript(TRANSCRIPT_1)
        results.append(("Parenting Styles Transcript", r1))
    except Exception as e:
        logger.error(f"❌ Transcript 1 failed: {e}")

    # --- Ingest Transcript 2: Sleep Training ---
    try:
        r2 = ingest_transcript(TRANSCRIPT_2)
        results.append(("Sleep Training Transcript", r2))
    except Exception as e:
        logger.error(f"❌ Transcript 2 failed: {e}")

    # --- Ingest PDF Book: It's Your Baby ---
    PDF_PATH = os.path.join(
        os.path.dirname(__file__), '..', 'docs',
        '_OceanofPDF.com_Its_Your_Baby_-_Dr_Saroja_Balan.pdf'
    )

    BOOK_METADATA = {
        "source_type": "book",
        "title": "It's Your Baby — Dr. Saroja Balan",
        "author_or_channel": "Dr. Saroja Balan",
        "url_or_identifier": "its_your_baby_saroja_balan_pdf",
        "global_summary": "Comprehensive guide on infant and child care by Dr. Saroja Balan, covering newborn care, feeding, sleep, growth milestones, common illnesses, vaccinations, and practical parenting advice for Indian families."
    }

    try:
        r3 = ingest_pdf_book(PDF_PATH, BOOK_METADATA)
        results.append(("It's Your Baby (PDF)", r3))
    except Exception as e:
        logger.error(f"❌ Book ingestion failed: {e}")

    # --- Summary ---
    logger.info("=" * 60)
    logger.info("📊 INGESTION SUMMARY")
    logger.info("=" * 60)
    for name, result in results:
        logger.info(f"  ✅ {name}: {result['chunks_inserted']} chunks (source: {result['source_id']})")
    logger.info("=" * 60)
    logger.info("🎯 INGESTION COMPLETE — Knowledge Hub is ready.")
