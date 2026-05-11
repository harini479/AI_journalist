import os
import re
import json
import logging
import httpx
import base64
from datetime import datetime, timezone
from typing import Optional, List

from supabase import create_client, Client
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

from .prompts import (
    JOURNALIST_BASE_PERSONA, 
    THEME_EXTRACTION_PROMPT, 
    SCRIPT_CRAFTING_PROMPT, 
    SCRIPT_AWARE_EVALUATION_PROMPT, 
    GENERATION_PHASE_PROMPT,
    INTENT_CLASSIFIER_PROMPT
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

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

app = FastAPI(title="AI Journalist Platform - Backend")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AI components
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
llm_fast = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, max_tokens=30)
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

# Constants
DEFAULT_TOPIC = "Technical Innovation and Scaling"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K_RAG = 4

# Deepgram API Key
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

class InterviewRequest(BaseModel):
    expert_answer: str
    user_session_id: str
    topic: Optional[str] = DEFAULT_TOPIC
    input_source: Optional[str] = "text"

class YoutubeIngestRequest(BaseModel):
    url: str

class PrepareRequest(BaseModel):
    user_session_id: str
    topic: Optional[str] = DEFAULT_TOPIC

def fetch_youtube_transcript(url: str) -> str:
    """Fetches transcript for a YouTube video URL."""
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if not video_id_match:
        raise ValueError("Invalid YouTube URL")
    video_id = video_id_match.group(1)
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.fetch(video_id, languages=['en', 'hi', 'te'])
    except Exception as e:
        try:
            transcripts = api.list(video_id)
            transcript_list = transcripts.find_transcript(['en', 'hi', 'te']).fetch()
        except:
            transcripts = api.list(video_id)
            transcript_list = next(iter(transcripts)).fetch()
    full_text = " ".join([item.text for item in transcript_list])
    return full_text, video_id

def hybrid_rag_fetch(query: str, top_k: int = 4) -> dict:
    """Fetches context from Supabase with metadata."""
    try:
        query_embedding = embeddings_model.embed_query(query)
        res = supabase.rpc("match_knowledge_chunks", {
            "query_embedding": query_embedding,
            "match_threshold": 0.3,
            "match_count": top_k
        }).execute()
        chunks = res.data or []
        if not chunks:
            res_kw = supabase.table("knowledge_chunks").select("*, knowledge_sources(title, source_type)").ilike("content", f"%{query[:15]}%").limit(top_k).execute()
            chunks = res_kw.data or []
        context_parts = []
        chunks_metadata = []
        for c in chunks:
            context_parts.append(c['content'])
            chunks_metadata.append({
                "chunk_id": c.get('id'),
                "source_title": c.get('knowledge_sources', {}).get('title', 'Unknown'),
                "source_type": c.get('knowledge_sources', {}).get('source_type', 'unknown'),
                "location_marker": c.get('location_marker', ''),
                "content": c['content'][:200] + "..."
            })
        return {
            "context_text": "\n\n".join(context_parts),
            "chunks_used": chunks_metadata
        }
    except Exception as e:
        logger.error(f"RAG fetch error: {e}")
        return {"context_text": "", "chunks_used": []}

async def research_scan() -> dict:
    """Samples chunks from knowledge sources."""
    try:
        sources = supabase.table("knowledge_sources").select("id, title, source_type").execute()
        briefing = []
        for s in sources.data:
            chunks = supabase.table("knowledge_chunks").select("content, location_marker").eq("source_id", s["id"]).limit(30).execute()
            if not chunks.data: continue
            total = len(chunks.data)
            indices = [0, total // 2, total - 1]
            for idx in set(indices):
                if idx < total:
                    briefing.append({
                        "source_title": s["title"],
                        "source_type": s["source_type"],
                        "location": chunks.data[idx]["location_marker"],
                        "content": chunks.data[idx]["content"][:400]
                    })
        return {"briefing": json.dumps(briefing, indent=2), "count": len(briefing)}
    except Exception as e:
        logger.error(f"Research scan error: {e}")
        return {"briefing": "[]", "count": 0}

@app.post("/ingest-youtube")
async def ingest_youtube_endpoint(request: YoutubeIngestRequest):
    try:
        raw_text, video_id = fetch_youtube_transcript(request.url)
        source_res = supabase.table("knowledge_sources").insert({
            "source_type": "youtube",
            "title": f"YouTube Video: {video_id}",
            "url_or_identifier": request.url
        }).execute()
        source_id = source_res.data[0]['id']
        chunks = [raw_text[i:i+CHUNK_SIZE] for i in range(0, len(raw_text), CHUNK_SIZE - CHUNK_OVERLAP)]
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
        return {"status": "success", "message": f"Ingested {len(chunks)} chunks.", "source_id": source_id}
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    if not DEEPGRAM_API_KEY:
        raise HTTPException(status_code=500, detail="Deepgram API key not configured.")
    try:
        audio_bytes = await audio.read()
        if not audio_bytes or len(audio_bytes) < 100:
            logger.warning(f"Empty or tiny audio received: {len(audio_bytes)} bytes")
            return {"transcript": ""}
        
        logger.info(f"Transcribing audio: {len(audio_bytes)} bytes, type={audio.content_type}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=en",
                headers={"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": audio.content_type or "audio/webm"},
                content=audio_bytes,
            )
        if resp.status_code != 200:
            logger.error(f"Deepgram API error: {resp.status_code} - {resp.text[:200]}")
            raise HTTPException(status_code=502, detail=f"Deepgram API error: {resp.status_code}")
        transcript = resp.json().get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
        if not transcript:
            logger.warning("Deepgram returned empty transcript")
        return {"transcript": transcript}
    except httpx.TimeoutException:
        logger.error("Deepgram request timed out")
        raise HTTPException(status_code=504, detail="Transcription timed out. Please try again.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {type(e).__name__}")

@app.post("/prepare-interview")
async def prepare_interview_endpoint(request: PrepareRequest):
    try:
        session_id = request.user_session_id
        topic = request.topic or DEFAULT_TOPIC
        scan_data = await research_scan()
        briefing = scan_data["briefing"]

        # Theme Extraction
        theme_res = llm.invoke(THEME_EXTRACTION_PROMPT.format(research_briefing=briefing))
        cleaned_themes = theme_res.content.strip()
        if "```json" in cleaned_themes: cleaned_themes = cleaned_themes.split("```json")[1].split("```")[0].strip()
        themes_data = json.loads(cleaned_themes)

        # Script Crafting
        script_res = llm.invoke(SCRIPT_CRAFTING_PROMPT.format(themes=json.dumps(themes_data), research_briefing=briefing))
        cleaned_script = script_res.content.strip()
        if "```json" in cleaned_script: cleaned_script = cleaned_script.split("```json")[1].split("```")[0].strip()
        script_data = json.loads(cleaned_script)

        total_q = 0
        if script_data.get("interview_arc"):
            for phase in script_data["interview_arc"].values():
                total_q += len(phase.get("questions", []))

        # Delete any existing script for this session, then insert fresh
        supabase.table("interview_scripts").delete().eq("session_id", session_id).execute()
        supabase.table("interview_scripts").insert({
            "session_id": session_id,
            "themes": themes_data,
            "full_script": script_data,
            "research_briefing": scan_data,
            "total_questions": total_q,
            "status": "draft"
        }).execute()

        return {"status": "success", "themes": themes_data, "script": script_data, "total_questions": total_q}
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

        # --- Ensure session exists in DB, get the DB UUID ---
        db_uuid = ensure_session(session_id, topic)

        # --- Save expert's answer to DB (if not empty) ---
        if expert_answer:
            save_message(db_uuid, "expert", expert_answer, request.input_source or "text")

        script_res = supabase.table("interview_scripts").select("*").eq("session_id", session_id).execute()
        if not script_res.data:
            result = await reactive_generate_question(request, formatted_persona)
            save_message(db_uuid, "ai", result["question"], "system", result.get("decision"))
            return result
        
        script_record = script_res.data[0]
        full_script = script_record["full_script"]
        completed_count = script_record.get("questions_completed", 0)
        
        all_questions = []
        for phase in ["phase_1_warmup", "phase_2_deep_dives", "phase_3_challenge", "phase_4_synthesis"]:
            phase_data = full_script.get("interview_arc", {}).get(phase, {})
            all_questions.extend(phase_data.get("questions", []))
        total_q = len(all_questions)
        
        if not expert_answer:
            first_q = all_questions[0]["question_text"] if all_questions else "Tell me about your expertise."
            result = {"question": first_q, "script_progress": f"1/{total_q}", "decision": {"action": "start_script", "internal_monologue": "Starting interview."}}
            save_message(db_uuid, "ai", first_q, "system", result["decision"])
            return result

        current_q_obj = all_questions[completed_count] if completed_count < total_q else all_questions[-1]
        
        # --- LLM INTENT CLASSIFICATION (understands meaning, not keywords) ---
        intent_res = llm_fast.invoke(INTENT_CLASSIFIER_PROMPT.format(
            current_question=current_q_obj["question_text"],
            expert_answer=expert_answer
        ))
        intent_json = intent_res.content.strip()
        if "```json" in intent_json: intent_json = intent_json.split("```json")[1].split("```")[0].strip()
        try:
            intent_data = json.loads(intent_json)
        except json.JSONDecodeError:
            intent_data = {"intent": "substantive"}
        
        is_skip_intent = intent_data.get("intent") == "skip"
        logger.info(f"Intent classification: {intent_data.get('intent')} | Answer: '{expert_answer[:80]}...'")
        
        if is_skip_intent:
            new_completed = min(completed_count + 1, total_q)
            supabase.table("interview_scripts").update({"questions_completed": new_completed}).eq("session_id", session_id).execute()
            
            if new_completed < total_q:
                next_q = all_questions[new_completed]
                decision = {
                    "next_action": "next_script_question",
                    "scripted_question_resolved": True,
                    "internal_monologue": f"Expert signaled skip intent. Moving to Q{new_completed + 1}.",
                    "tangent_detected": {"exists": False}
                }
                save_message(db_uuid, "ai", next_q["question_text"], "system", decision)
                return {
                    "question": next_q["question_text"],
                    "script_progress": f"{new_completed + 1}/{total_q}",
                    "decision": decision,
                    "chunks_used": []
                }
            else:
                end_msg = "Thank you. We've covered all the questions. Your insights have been invaluable."
                end_decision = {"next_action": "interview_complete"}
                save_message(db_uuid, "ai", end_msg, "system", end_decision)
                supabase.table("interview_scripts").update({"status": "completed"}).eq("session_id", session_id).execute()
                return {"question": end_msg, "script_progress": f"{total_q}/{total_q}", "decision": end_decision}

        # --- LLM EVALUATION (only if NOT a skip) ---
        rag_data = hybrid_rag_fetch(expert_answer)
        
        eval_res = llm.invoke(SCRIPT_AWARE_EVALUATION_PROMPT.format(
            current_script_question=current_q_obj["question_text"],
            expert_answer=expert_answer,
            db_context=rag_data["context_text"],
            completed=completed_count,
            total=total_q,
            tangent_turns_remaining=2
        ))
        cleaned_json = eval_res.content.strip()
        if "```json" in cleaned_json: cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
        eval_data = json.loads(cleaned_json)

        new_completed = completed_count + (1 if eval_data.get("scripted_question_resolved") else 0)
        new_completed = min(new_completed + len(eval_data.get("pruned_questions", [])), total_q)

        supabase.table("interview_scripts").update({"questions_completed": new_completed}).eq("session_id", session_id).execute()

        next_action = eval_data.get("next_action", "next_script_question")
        
        # --- DIRECT SCRIPT QUESTION (no LLM rewrite) ---
        if next_action == "next_script_question" and new_completed < total_q:
            next_q = all_questions[new_completed]
            bridge = eval_data.get("bridge_suggestion", "")
            question_text = f"{bridge} {next_q['question_text']}" if bridge else next_q["question_text"]
            save_message(db_uuid, "ai", question_text, "system", eval_data)
            return {
                "question": question_text,
                "script_progress": f"{new_completed + 1}/{total_q}",
                "decision": eval_data,
                "chunks_used": rag_data["chunks_used"]
            }
        
        # --- GENERATION PROMPT (only for drill_down, follow_tangent, bridge_back) ---
        if next_action == "follow_tangent":
            scenario = f"Follow tangent: {eval_data.get('tangent_detected', {}).get('topic')}"
        elif next_action == "bridge_back_to_script" and new_completed < total_q:
            scenario = f"The expert went on a tangent. Bridge back naturally and ask: {all_questions[new_completed]['question_text']}"
        elif next_action == "drill_down":
            scenario = f"The expert gave a surface-level answer to: '{current_q_obj['question_text']}'. Push them for the specific war story, the exact moment, or the step-by-step tactic."
        else:
            if new_completed < total_q:
                q_text = all_questions[new_completed]["question_text"]
                save_message(db_uuid, "ai", q_text, "system", eval_data)
                return {
                    "question": q_text,
                    "script_progress": f"{new_completed + 1}/{total_q}",
                    "decision": eval_data,
                    "chunks_used": rag_data["chunks_used"]
                }
            else:
                end_msg = "Thank you. We've covered every question in the script. Your expertise has been invaluable."
                end_decision = {"next_action": "interview_complete"}
                save_message(db_uuid, "ai", end_msg, "system", end_decision)
                supabase.table("interview_scripts").update({"status": "completed"}).eq("session_id", session_id).execute()
                return {"question": end_msg, "script_progress": f"{total_q}/{total_q}", "decision": end_decision}

        gen_res = llm.invoke(GENERATION_PHASE_PROMPT.format(persona=formatted_persona, scenario_instruction=scenario, expert_answer=expert_answer))
        generated_q = gen_res.content.strip()
        save_message(db_uuid, "ai", generated_q, "system", eval_data)
        
        return {
            "question": generated_q,
            "script_progress": f"{new_completed + 1}/{total_q}",
            "decision": eval_data,
            "chunks_used": rag_data["chunks_used"]
        }
    except Exception as e:
        logger.error(f"Error in generate-question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def reactive_generate_question(request, persona):
    rag_data = hybrid_rag_fetch(request.expert_answer)
    gen_res = llm.invoke(GENERATION_PHASE_PROMPT.format(persona=persona, scenario_instruction="Reactive follow-up.", expert_answer=request.expert_answer))
    result = {"question": gen_res.content.strip(), "script_progress": "Reactive", "decision": {"action": "reactive_fallback"}}
    return result

# --- PERSISTENCE HELPERS ---

def ensure_session(session_id: str, topic: str) -> str:
    """Create a session row if it doesn't exist. Returns the DB row UUID (id)."""
    try:
        existing = supabase.table("conversation_sessions").select("id").eq("session_id", session_id).execute()
        if existing.data:
            return existing.data[0]["id"]
        else:
            from datetime import datetime, timezone
            res = supabase.table("conversation_sessions").insert({
                "session_id": session_id,
                "topic": topic,
                "status": "active",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total_messages": 0
            }).execute()
            logger.info(f"Created new session: {session_id}")
            return res.data[0]["id"]
    except Exception as e:
        logger.error(f"Failed to ensure session: {e}")
        return ""

def save_message(db_session_id: str, role: str, content: str, input_source: str = "text", metadata: dict = None):
    """Save a single message to the database. db_session_id is the UUID primary key from conversation_sessions."""
    if not db_session_id:
        logger.error("Cannot save message: no db_session_id")
        return
    try:
        # Get current message count to set message_index
        count_res = supabase.table("conversation_messages").select("id", count="exact").eq("session_id", db_session_id).execute()
        msg_index = count_res.count if count_res.count else 0
        
        msg_data = {
            "session_id": db_session_id,
            "message_index": msg_index,
            "role": role,
            "content": content,
            "input_source": input_source,
        }
        if metadata:
            msg_data["metadata"] = metadata
        
        supabase.table("conversation_messages").insert(msg_data).execute()
        
        # Update total_messages in session
        supabase.table("conversation_sessions").update({
            "total_messages": msg_index + 1
        }).eq("id", db_session_id).execute()
        
        logger.info(f"Saved message #{msg_index} ({role}) for session {db_session_id[:8]}")
    except Exception as e:
        logger.error(f"Failed to save message: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9120)
