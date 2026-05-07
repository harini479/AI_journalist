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
from backend.prompts import (
    JOURNALIST_BASE_PERSONA, 
    THEME_EXTRACTION_PROMPT, 
    SCRIPT_CRAFTING_PROMPT, 
    SCRIPT_AWARE_EVALUATION_PROMPT, 
    GENERATION_PHASE_PROMPT
)

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

# Constants for Dynamic Configuration
DEFAULT_TOPIC = "Technical Innovation and Scaling"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K_RAG = 3
MAX_BACKLOG_SIZE = 5

class InterviewRequest(BaseModel):
    expert_answer: str
    user_session_id: str
    topic: Optional[str] = DEFAULT_TOPIC

class YoutubeIngestRequest(BaseModel):
    url: str

class PrepareRequest(BaseModel):
    user_session_id: str
    topic: Optional[str] = DEFAULT_TOPIC

def fetch_youtube_transcript(url: str) -> str:
    """Fetches transcript for a YouTube video URL."""
    from youtube_transcript_api import YouTubeTranscriptApi
    import re
    
    # Extract video ID
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if not video_id_match:
        raise ValueError("Invalid YouTube URL")
    
    video_id = video_id_match.group(1)
    
    # Use instance-based fetch
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.fetch(video_id, languages=['en', 'hi', 'te'])
    except Exception as e:
        logger.warning(f"Failed to fetch specific languages, attempting list-based discovery: {e}")
        try:
            transcripts = api.list(video_id)
            transcript_list = transcripts.find_transcript(['en', 'hi', 'te']).fetch()
        except:
            # Last resort: Get the first available transcript
            transcripts = api.list(video_id)
            transcript_list = next(iter(transcripts)).fetch()
        
    # Combine segments
    full_text = " ".join([item.text for item in transcript_list])
    return full_text, video_id

def hybrid_rag_fetch(query: str) -> str:
    """
    Advanced Hybrid RAG: Combines Semantic (Vector) + Exact (FTS) search.
    """
    try:
        # 1. Semantic Search (Vector)
        query_vector = embeddings_model.embed_query(query)
        vector_res = supabase.rpc("match_knowledge_chunks", {
            "query_embedding": query_vector,
            "match_threshold": 0.5,
            "match_count": TOP_K_RAG
        }).execute()
        
        # 2. Exact Search (FTS) - Fallback or Hybrid
        fts_res = supabase.table("knowledge_chunks") \
            .select("content") \
            .text_search("content", query) \
            .limit(TOP_K_RAG) \
            .execute()
        
        # Combine results
        contexts = []
        if vector_res.data:
            contexts.extend([d['content'] for d in vector_res.data])
        if fts_res.data:
            contexts.extend([d['content'] for d in fts_res.data])
            
        return "\n---\n".join(list(set(contexts))[:TOP_K_RAG]) or "No relevant technical context found."
    except Exception as e:
        logger.error(f"RAG fetch error: {e}")
        # Fallback to simple ILIKE if RPC match_knowledge_chunks isn't created yet
        fallback = supabase.table("knowledge_chunks").select("content").ilike("content", f"%{query[:15]}%").limit(1).execute()
        return fallback.data[0]['content'] if fallback.data else "Context unavailable."

async def research_scan() -> dict:
    """
    Scans the knowledge base to prepare a briefing for theme extraction.
    Fetches chunks from start, middle, and end of each source.
    """
    try:
        sources_res = supabase.table("knowledge_sources").select("id, title, source_type").execute()
        if not sources_res.data:
            return {"briefing": "No knowledge sources found.", "chunks_sampled": 0}

        briefing_items = []
        for source in sources_res.data:
            chunks_res = supabase.table("knowledge_chunks") \
                .select("content, location_marker") \
                .eq("source_id", source["id"]) \
                .order("chunk_index") \
                .execute()
            
            if not chunks_res.data:
                continue

            total = len(chunks_res.data)
            # Sample 3 chunks per source: start, middle, end
            indices = [0, total // 2, total - 1]
            unique_indices = sorted(list(set(indices)))

            for idx in unique_indices:
                chunk = chunks_res.data[idx]
                briefing_items.append({
                    "source_title": source["title"],
                    "source_type": source["source_type"],
                    "location": chunk["location_marker"],
                    "content": chunk["content"][:400] + "..." # Keep it concise for prompt
                })

        return {
            "briefing": json.dumps(briefing_items, indent=2),
            "chunks_sampled": len(briefing_items),
            "sources_scanned": len(sources_res.data)
        }
    except Exception as e:
        logger.error(f"Research scan error: {e}")
        return {"briefing": f"Error during research scan: {e}", "chunks_sampled": 0}

@app.post("/ingest-youtube")
async def ingest_youtube_endpoint(request: YoutubeIngestRequest):
    try:
        logger.info(f"Hierarchical Ingestion started for: {request.url}")
        
        # 1. Fetch Raw Transcript
        raw_text, video_id = fetch_youtube_transcript(request.url)
        
        # 2. Create Parent Source
        # Note: In a production app, we'd use a YouTube API client here to get the actual title/channel
        source_res = supabase.table("knowledge_sources").insert({
            "source_type": "youtube",
            "title": f"YouTube Video: {video_id}",
            "url_or_identifier": request.url
        }).execute()
        
        if not source_res.data:
            raise Exception("Failed to create knowledge source")
        source_id = source_res.data[0]['id']
        
        # 3. Dynamic Chunking
        chunks = [raw_text[i:i+CHUNK_SIZE] for i in range(0, len(raw_text), CHUNK_SIZE - CHUNK_OVERLAP)]
        
        # 4. Generate Embeddings & Insert Chunks
        chunk_data = []
        for idx, content in enumerate(chunks):
            vector = embeddings_model.embed_query(content)
            chunk_data.append({
                "source_id": source_id,
                "content": content,
                "embedding": vector,
                "chunk_index": idx
            })
        
        supabase.table("knowledge_chunks").insert(chunk_data).execute()
        
        return {
            "status": "success",
            "message": f"Ingested {len(chunks)} dynamic chunks into Supabase.",
            "source_id": source_id
        }
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/prepare-interview")
async def prepare_interview_endpoint(request: PrepareRequest):
    try:
        session_id = request.user_session_id
        topic = request.topic or DEFAULT_TOPIC
        
        logger.info(f"Preparing interview script for session: {session_id} on topic: {topic}")

        # 1. Research Scan
        scan_data = await research_scan()
        briefing = scan_data["briefing"]

        # 2. Theme Extraction
        theme_prompt = THEME_EXTRACTION_PROMPT.format(research_briefing=briefing)
        theme_response = llm.invoke(theme_prompt)
        
        try:
            cleaned_themes = theme_response.content.strip()
            if "```json" in cleaned_themes:
                cleaned_themes = cleaned_themes.split("```json")[1].split("```")[0].strip()
            themes_data = json.loads(cleaned_themes)
        except Exception as e:
            logger.error(f"Failed to parse themes JSON: {e}")
            themes_data = []

        # 3. Script Crafting
        script_prompt = SCRIPT_CRAFTING_PROMPT.format(
            themes=json.dumps(themes_data, indent=2),
            research_briefing=briefing
        )
        script_response = llm.invoke(script_prompt)

        try:
            cleaned_script = script_response.content.strip()
            if "```json" in cleaned_script:
                cleaned_script = cleaned_script.split("```json")[1].split("```")[0].strip()
            script_data = json.loads(cleaned_script)
        except Exception as e:
            logger.error(f"Failed to parse script JSON: {e}")
            script_data = {}

        # 4. Save to interview_scripts table
        total_q = 0
        if script_data.get("interview_arc"):
            for phase in script_data["interview_arc"].values():
                total_q += len(phase.get("questions", []))

        supabase.table("interview_scripts").upsert({
            "session_id": session_id,
            "themes": themes_data,
            "full_script": script_data,
            "research_briefing": scan_data,
            "total_questions": total_q,
            "status": "draft"
        }).execute()

        return {
            "status": "success",
            "themes": themes_data,
            "script": script_data,
            "total_questions": total_q
        }
    except Exception as e:
        logger.error(f"Preparation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-question")
async def generate_next_question_endpoint(request: InterviewRequest):
    try:
        session_id = request.user_session_id
        expert_answer = request.expert_answer.strip()
        topic = request.topic or DEFAULT_TOPIC
        formatted_persona = JOURNALIST_BASE_PERSONA.replace("{topic}", topic)

        # 1. Load Script State
        script_res = supabase.table("interview_scripts").select("*").eq("session_id", session_id).execute()
        if not script_res.data:
            # Fallback to reactive mode if no script exists
            return await reactive_generate_question(request, formatted_persona)
        
        script_record = script_res.data[0]
        full_script = script_record["full_script"]
        completed_count = script_record.get("questions_completed", 0)
        
        # Flatten questions for easier indexing
        all_questions = []
        for phase in ["phase_1_warmup", "phase_2_deep_dives", "phase_3_challenge", "phase_4_synthesis"]:
            phase_data = full_script.get("interview_arc", {}).get(phase, {})
            all_questions.extend(phase_data.get("questions", []))
        
        total_q = len(all_questions)
        
        if not expert_answer:
            # FIRST HOOK from script
            first_q = all_questions[0]["question_text"] if all_questions else "Tell me about your expertise."
            return {
                "question": first_q,
                "script_progress": f"1/{total_q}",
                "decision": {"action": "start_script", "internal_monologue": "Starting the interview with the first scripted question."}
            }

        # 2. Identify Current Question
        current_q_obj = all_questions[completed_count] if completed_count < total_q else all_questions[-1]
        
        # 3. RETRIEVAL & EVALUATION
        db_context = hybrid_rag_fetch(expert_answer)
        
        eval_prompt = SCRIPT_AWARE_EVALUATION_PROMPT.format(
            current_script_question=current_q_obj["question_text"],
            expert_answer=expert_answer,
            db_context=db_context,
            completed=completed_count,
            total=total_q,
            tangent_turns_remaining=2 # Simplified for now
        )
        
        eval_response = llm.invoke(eval_prompt)
        try:
            cleaned_json = eval_response.content.strip()
            if "```json" in cleaned_json:
                cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
            eval_data = json.loads(cleaned_json)
        except:
            eval_data = {"scripted_question_resolved": True, "next_action": "next_script_question", "internal_monologue": "Logic fallback."}

        # 4. State Update
        new_completed_count = completed_count
        if eval_data.get("scripted_question_resolved"):
            new_completed_count += 1
        
        # Check for pruned questions (expert naturally answered future questions)
        pruned = eval_data.get("pruned_questions", [])
        new_completed_count += len(pruned)
        new_completed_count = min(new_completed_count, total_q)

        supabase.table("interview_scripts").update({
            "questions_completed": new_completed_count
        }).eq("session_id", session_id).execute()

        # 5. GENERATION PHASE
        next_action = eval_data.get("next_action", "next_script_question")
        
        if next_action == "next_script_question" and new_completed_count < total_q:
            target_question = all_questions[new_completed_count]["question_text"]
            scenario = f"The previous topic is resolved. Move to the next scripted question: {target_question}"
        elif next_action == "follow_tangent":
            scenario = f"The expert opened a high-value tangent: {eval_data.get('tangent_detected', {}).get('topic')}. Ask a follow-up to explore this."
        elif next_action == "bridge_back_to_script" and new_completed_count < total_q:
            target_question = all_questions[new_completed_count]["question_text"]
            scenario = f"Bridge the current discussion back to the script. Next question: {target_question}. {eval_data.get('bridge_suggestion', '')}"
        elif next_action == "drill_down":
            scenario = "The expert's answer was surface-level. Ask a targeted drill-down question to extract more depth."
        else:
            scenario = "The interview is reaching its natural conclusion. Ask a final synthesis question."

        gen_prompt = GENERATION_PHASE_PROMPT.format(
            persona=formatted_persona,
            scenario_instruction=scenario,
            expert_answer=expert_answer
        )
        
        final_response = llm.invoke(gen_prompt)
        
        return {
            "question": final_response.content.strip(),
            "script_progress": f"{new_completed_count + 1}/{total_q}",
            "decision": eval_data
        }
    except Exception as e:
        logger.error(f"Error in generate-question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def reactive_generate_question(request, persona):
    """Fallback reactive mode if no script exists."""
    expert_answer = request.expert_answer.strip()
    db_context = hybrid_rag_fetch(expert_answer)
    
    # Simple fallback scenario
    scenario = "No script found. Reactively follow up on the expert's answer."
    gen_prompt = GENERATION_PHASE_PROMPT.format(
        persona=persona,
        scenario_instruction=scenario,
        expert_answer=expert_answer
    )
    response = llm.invoke(gen_prompt)
    return {
        "question": response.content.strip(),
        "script_progress": "Reactive",
        "decision": {"action": "reactive_fallback", "internal_monologue": "No script found for this session."}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
