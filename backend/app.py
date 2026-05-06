import os
import logging
from typing import Optional
from supabase import create_client, Client
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import json
from langchain_openai import OpenAIEmbeddings
from prompts import JOURNALIST_BASE_PERSONA, EVALUATION_PHASE_PROMPT, GENERATION_PHASE_PROMPT

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

# Initialize AI components
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

class InterviewRequest(BaseModel):
    expert_answer: str
    user_session_id: str
    topic: Optional[str] = "Clinical Scaling of SGLT2 Inhibitors"

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

def hybrid_rag_fetch(query: str, top_k: int = 2) -> str:
    """
    Advanced Hybrid RAG: Combines Semantic (Vector) + Exact (FTS) search.
    """
    try:
        # 1. Semantic Search (Vector)
        query_vector = embeddings_model.embed_query(query)
        vector_res = supabase.rpc("match_knowledge_chunks", {
            "query_embedding": query_vector,
            "match_threshold": 0.5,
            "match_count": top_k
        }).execute()
        
        # 2. Exact Search (FTS) - Fallback or Hybrid
        fts_res = supabase.table("knowledge_chunks") \
            .select("content") \
            .text_search("content", query) \
            .limit(top_k) \
            .execute()
        
        # Combine results
        contexts = []
        if vector_res.data:
            contexts.extend([d['content'] for d in vector_res.data])
        if fts_res.data:
            contexts.extend([d['content'] for d in fts_res.data])
            
        return "\n---\n".join(list(set(contexts))[:3]) or "No relevant technical context found."
    except Exception as e:
        logger.error(f"RAG fetch error: {e}")
        # Fallback to simple ILIKE if RPC match_knowledge_chunks isn't created yet
        fallback = supabase.table("knowledge_chunks").select("content").ilike("content", f"%{query[:15]}%").limit(1).execute()
        return fallback.data[0]['content'] if fallback.data else "Context unavailable."

@app.post("/ingest-youtube")
async def ingest_youtube_endpoint(request: YoutubeIngestRequest):
    try:
        logger.info(f"Hierarchical Ingestion started for: {request.url}")
        
        # 1. Fetch Raw Transcript
        raw_text = fetch_youtube_transcript(request.url)
        
        # 2. Create Parent Source
        source_res = supabase.table("knowledge_sources").insert({
            "source_type": "youtube",
            "title": f"YouTube Video: {request.url[-11:]}",
            "url_or_identifier": request.url
        }).execute()
        
        if not source_res.data:
            raise Exception("Failed to create knowledge source")
        source_id = source_res.data[0]['id']
        
        # 3. Chunking (Simple 1000-char chunks for demo)
        chunks = [raw_text[i:i+1000] for i in range(0, len(raw_text), 800)]
        
        # 4. Generate Embeddings & Insert Chunks
        chunk_data = []
        for content in chunks:
            vector = embeddings_model.embed_query(content)
            chunk_data.append({
                "source_id": source_id,
                "content": content,
                "embedding": vector
            })
        
        supabase.table("knowledge_chunks").insert(chunk_data).execute()
        
        return {
            "status": "success",
            "message": f"Ingested {len(chunks)} hierarchical chunks into Supabase.",
            "source_id": source_id
        }
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-question")
async def generate_next_question_endpoint(request: InterviewRequest):
    try:
        session_id = request.user_session_id
        expert_answer = request.expert_answer.strip()
        
        # 1. Retrieve Current Session State (Backlog)
        try:
            session_res = supabase.table("interview_sessions").select("question_backlog").eq("session_id", session_id).execute()
            backlog = session_res.data[0]['question_backlog'] if (session_res.data and len(session_res.data) > 0) else []
        except Exception as e:
            logger.warning(f"Could not retrieve session from Supabase: {e}")
            backlog = []
        
        if not expert_answer:
            # FIRST HOOK LOGIC
            first_hook_prompt = f"{JOURNALIST_BASE_PERSONA}\n\nAsk a provocative opening question to start an interview about: {request.topic}"
            response = llm.invoke(first_hook_prompt)
            return {"question": response.content.strip(), "backlog": backlog}

        # 2. RETRIEVAL: Fetch Context from Hierarchical RAG
        db_context = hybrid_rag_fetch(expert_answer)
        
        # 3. EVALUATION PHASE: Internal Monologue (JSON)
        eval_prompt = EVALUATION_PHASE_PROMPT.format(
            expert_answer=expert_answer,
            db_context=db_context,
            current_backlog=json.dumps(backlog)
        )
        eval_response = llm.invoke(eval_prompt)
        
        try:
            cleaned_json = eval_response.content.strip()
            if "```json" in cleaned_json:
                cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
            eval_data = json.loads(cleaned_json)
        except:
            eval_data = {"pruned_questions": [], "new_gaps_found": [], "sync_found": {"is_synced": False}}

        # 4. STATE UPDATE: Sync Backlog
        remaining_backlog = [q for q in backlog if q not in eval_data.get("pruned_questions", [])]
        remaining_backlog.extend(eval_data.get("new_gaps_found", []))
        remaining_backlog = remaining_backlog[:5]
        
        try:
            supabase.table("interview_sessions").upsert({
                "session_id": session_id,
                "question_backlog": remaining_backlog
            }).execute()
        except Exception as e:
            logger.warning(f"Could not save session state: {e}")

        # 5. GENERATION PHASE: Final Question
        if eval_data.get("sync_found", {}).get("is_synced"):
            target_q = eval_data["sync_found"]["target_backlog_question"]
            scenario = f"The expert naturally synced with a backlogged topic. BRIDGE their answer to this question: {target_q}"
        elif eval_data.get("new_gaps_found"):
            scenario = f"A new conceptual gap was found: {eval_data['new_gaps_found'][0]}. Ask a targeted follow-up."
        else:
            scenario = "No specific gap found. Ask a general follow-up to push the narrative further."

        gen_prompt = GENERATION_PHASE_PROMPT.format(
            persona=JOURNALIST_BASE_PERSONA,
            scenario_instruction=scenario,
            expert_answer=expert_answer
        )
        
        final_response = llm.invoke(gen_prompt)
        return {
            "question": final_response.content.strip(),
            "backlog": remaining_backlog,
            "internal_logic": eval_data
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
