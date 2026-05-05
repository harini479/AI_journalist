import os
import logging
from typing import Optional
from supabase import create_client, Client
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from prompts import JOURNALIST_BASE_PERSONA, FIRST_HOOK_TEMPLATE, FOLLOW_UP_LOOP_TEMPLATE

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path, override=True)
logger.info(f"Loading .env from: {os.path.abspath(env_path)}")

# Database Setup
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_DB_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Debugging the source
if SUPABASE_URL:
    logger.info(f"SUPABASE_URL resolved to: {SUPABASE_URL}")
else:
    logger.error("SUPABASE_URL NOT FOUND in environment or .env!")

if not SUPABASE_ANON_KEY:
    logger.error("SUPABASE_ANON_KEY NOT FOUND in environment or .env!")

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

app = FastAPI(title="AI Journalist Platform - Backend")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo purposes, allow all. In production, restrict to frontend URL.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

class InterviewRequest(BaseModel):
    expert_answer: str
    last_question: Optional[str] = None
    user_session_id: str

class YoutubeIngestRequest(BaseModel):
    url: str

def fetch_youtube_transcript(url: str) -> str:
    """Fetches transcript for a YouTube video URL."""
    from youtube_transcript_api import YouTubeTranscriptApi
    import re
    
    # Extract video ID
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if not video_id_match:
        raise ValueError("Invalid YouTube URL")
    
    video_id = video_id_match.group(1)
    
    # Use instance-based fetch (required by this version of the API)
    # We try English first, then fall back to common languages or auto-generated
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.fetch(video_id, languages=['en', 'hi', 'te'])
    except Exception as e:
        logger.warning(f"Failed to fetch specific languages, attempting list-based discovery: {e}")
        # Fallback: Just get whatever is available
        transcripts = api.list(video_id)
        transcript_list = transcripts.find_transcript(['en', 'hi', 'te']).fetch()
        
    # Combine segments
    full_text = " ".join([item.text for item in transcript_list])
    return full_text

def hybrid_rag_fetch(query: str, top_k: int = 1) -> str:
    """
    Implementation of Hybrid RAG fetch using Supabase Client.
    Uses text search on the transcripts table.
    """
    try:
        # Search using Supabase built-in text search
        # Note: This requires the 'transcripts_content_idx' we created earlier
        response = supabase.table("transcripts") \
            .select("content") \
            .text_search("content", query) \
            .range(0, top_k - 1) \
            .execute()
        
        if response.data:
            return response.data[0]['content']
            
        # Fallback to simple ILIKE search if text_search returns nothing
        fallback = supabase.table("transcripts") \
            .select("content") \
            .ilike("content", f"%{query[:20]}%") \
            .range(0, 0) \
            .execute()
            
        if fallback.data:
            return fallback.data[0]['content']

        return "No specific technical context found in the database for this query."
    except Exception as e:
        logger.error(f"Database fetch error: {e}")
        return "Database unavailable."

@app.post("/ingest-youtube")
async def ingest_youtube_endpoint(request: YoutubeIngestRequest):
    try:
        logger.info(f"Ingesting YouTube video: {request.url}")
        
        # 1. Fetch Transcript
        transcript = fetch_youtube_transcript(request.url)
        
        # 2. Save to Supabase via Client
        data = {
            "video_url": request.url,
            "content": transcript
        }
        supabase.table("transcripts").insert(data).execute()
        
        word_count = len(transcript.split())
        logger.info(f"Successfully persisted transcript to Supabase: {word_count} words.")
        
        return {
            "status": "success",
            "message": f"Successfully ingested {word_count} words. Data has been persisted to your Supabase Knowledge Hub via the Anon Key.",
            "preview": transcript[:500] + "..."
        }
        
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-question")
async def generate_next_question_endpoint(request: InterviewRequest):
    try:
        expert_answer = request.expert_answer.strip()
        
        # Determine if this is the First Hook or a Follow-up
        if not expert_answer:
            # ... (First Hook logic remains same)
            # Fetch the most recent transcript to use as the base for the First Hook
            response = supabase.table("transcripts") \
                .select("content") \
                .order("created_at", desc=True) \
                .range(0, 0) \
                .execute()
            
            if response.data:
                topic = f"the following knowledge base content: {response.data[0]['content'][:1000]}..."
            else:
                topic = "General Technical Thought-Leadership and Digital Transformation"
            
            prompt = FIRST_HOOK_TEMPLATE.format(
                persona=JOURNALIST_BASE_PERSONA,
                topic=topic
            )
        else:
            # SAVE TACIT KNOWLEDGE: Persist the Expert's Insight to Supabase
            try:
                insight_data = {
                    "session_id": request.user_session_id,
                    "question": request.last_question,
                    "answer": expert_answer
                }
                supabase.table("expert_insights").insert(insight_data).execute()
                logger.info("Tacit knowledge successfully persisted to expert_insights table.")
            except Exception as e:
                logger.error(f"Failed to persist tacit knowledge: {e}")

            # 1. Execute RAG fetch
            db_context = hybrid_rag_fetch(query=expert_answer, top_k=1)
            
            # 2. Assemble Follow-up
            prompt = FOLLOW_UP_LOOP_TEMPLATE.format(
                persona=JOURNALIST_BASE_PERSONA,
                db_context=db_context,
                expert_answer=expert_answer
            )
        
        # 3. Call LLM API
        response = llm.invoke(prompt)
        return {"question": response.content.strip()}
        
    except Exception as e:
        import traceback
        logger.error(f"Error generating question: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
