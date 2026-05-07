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

from prompts import (
    JOURNALIST_BASE_PERSONA, 
    EVALUATION_PHASE_PROMPT, 
    GENERATION_PHASE_PROMPT,
    THEME_EXTRACTION_PROMPT,
    SCRIPT_CRAFTING_PROMPT,
    SCRIPT_AWARE_EVALUATION_PROMPT
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

# Deepgram API Key
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# In-memory audit log storage (per session)
# Format: { session_id: [ {role, text, timestamp}, ... ] }
audit_logs: dict = {}

class InterviewRequest(BaseModel):
    expert_answer: str
    user_session_id: str
    topic: Optional[str] = "Enterprise Pre-Sales, Solutions Architecture & Deal Strategy"
    input_source: Optional[str] = "text"

class YoutubeIngestRequest(BaseModel):
    url: str

class PrepareInterviewRequest(BaseModel):
    session_id: str
    topic: str

def fetch_youtube_transcript(url: str) -> str:
    """Fetches transcript for a YouTube video URL."""
    
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

def normalize_question(q, index: int) -> dict:
    """Normalize a single question object so the frontend always finds the right fields."""
    try:
        # If the LLM returned a plain string instead of a dict
        if isinstance(q, str):
            return {
                "question_id": f"Q{index + 1}",
                "question_text": q,
                "emotional_trigger": "",
                "chunk_attribution": {"source_title": "Knowledge Hub", "chunk_content": "", "why_this_chunk": ""}
            }
        
        if not isinstance(q, dict):
            return {
                "question_id": f"Q{index + 1}",
                "question_text": str(q),
                "emotional_trigger": "",
                "chunk_attribution": {"source_title": "Knowledge Hub", "chunk_content": "", "why_this_chunk": ""}
            }
        
        normalized = {}
        
        # question_id
        normalized["question_id"] = q.get("question_id") or q.get("id") or q.get("q_id") or f"Q{index + 1}"
        
        # question_text — the most critical field
        normalized["question_text"] = (
            q.get("question_text") or q.get("text") or q.get("question") 
            or q.get("q_text") or q.get("prompt") or q.get("content") or ""
        )
        
        # emotional_trigger
        normalized["emotional_trigger"] = (
            q.get("emotional_trigger") or q.get("trigger") or q.get("emotion") 
            or q.get("emotional_anchor") or ""
        )
        
        # chunk_attribution - handle string, dict, list, or missing
        raw_attr = q.get("chunk_attribution") or q.get("attribution") or q.get("source") or {}
        if isinstance(raw_attr, str):
            raw_attr = {"source_title": raw_attr}
        elif isinstance(raw_attr, list):
            raw_attr = raw_attr[0] if raw_attr else {}
            if isinstance(raw_attr, str):
                raw_attr = {"source_title": raw_attr}
        if not isinstance(raw_attr, dict):
            raw_attr = {"source_title": "Knowledge Hub"}
            
        normalized["chunk_attribution"] = {
            "source_title": raw_attr.get("source_title") or raw_attr.get("title") or raw_attr.get("source") or "Knowledge Hub",
            "chunk_content": raw_attr.get("chunk_content") or raw_attr.get("content") or "",
            "why_this_chunk": raw_attr.get("why_this_chunk") or raw_attr.get("reasoning") or "",
        }
        
        # Keep any extra fields the LLM generated
        for k, v in q.items():
            if k not in normalized:
                normalized[k] = v
        
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize question {index}: {e}")
        return {
            "question_id": f"Q{index + 1}",
            "question_text": str(q) if q else "",
            "emotional_trigger": "",
            "chunk_attribution": {"source_title": "Knowledge Hub", "chunk_content": "", "why_this_chunk": ""}
        }

def normalize_script_phases(script_data: dict) -> dict:
    """
    Maps whatever keys the LLM returns into the 4 canonical phase keys
    AND normalizes every question object inside each phase.
    """
    arc = script_data.get("interview_arc", {})
    if not arc:
        for key in list(script_data.keys()):
            if "arc" in key.lower() or "phase" in key.lower():
                arc = script_data[key]
                break
    
    canonical = ["phase_1_foundation", "phase_2_tension", "phase_3_tactical", "phase_4_synthesis"]
    
    mapping = {
        "phase_1_foundation": ["phase_1_foundation", "phase_1_warmup", "phase_1", "foundation", "warmup", "warm_up", "origin", "basics"],
        "phase_2_tension": ["phase_2_tension", "phase_2_deep_dives", "phase_2", "tension", "deep_dives", "deep_dive", "friction", "conflict"],
        "phase_3_tactical": ["phase_3_tactical", "phase_3_challenge", "phase_3", "tactical", "tactical_playbook", "playbook", "challenge", "sop"],
        "phase_4_synthesis": ["phase_4_synthesis", "phase_4", "synthesis", "final", "conclusion", "wisdom", "distillation"],
    }
    
    normalized_arc = {}
    used_keys = set()
    
    for canon_key, aliases in mapping.items():
        for alias in aliases:
            for actual_key in arc:
                clean_key = actual_key.lower().replace(" ", "_").replace("-", "_")
                if clean_key == alias or alias in clean_key:
                    if actual_key not in used_keys:
                        normalized_arc[canon_key] = arc[actual_key]
                        used_keys.add(actual_key)
                        break
            if canon_key in normalized_arc:
                break
    
    remaining_arc_keys = [k for k in arc if k not in used_keys]
    missing_canonical = [k for k in canonical if k not in normalized_arc]
    for canon_key, actual_key in zip(missing_canonical, remaining_arc_keys):
        normalized_arc[canon_key] = arc[actual_key]
        used_keys.add(actual_key)
    
    # Now normalize every question inside each phase
    for phase_key, phase_data in normalized_arc.items():
        if isinstance(phase_data, dict) and "questions" in phase_data:
            phase_data["questions"] = [
                normalize_question(q, i) for i, q in enumerate(phase_data["questions"])
            ]
    
    script_data["interview_arc"] = normalized_arc
    
    # Log first question for debugging
    first_phase = normalized_arc.get("phase_1_foundation", {})
    first_qs = first_phase.get("questions", [])
    if first_qs:
        logger.info(f"Sample Q1 fields: {list(first_qs[0].keys())}")
        logger.info(f"Sample Q1 text: {first_qs[0].get('question_text', 'MISSING')[:80]}")
    
    return script_data

def hybrid_rag_fetch(query: str, top_k: int = 4) -> dict:
    """
    Fetches context from Supabase using vector and keyword search.
    Returns a dict with 'context_text' and 'chunks_used' metadata.
    """
    try:
        query_embedding = embeddings_model.embed_query(query)
        
        # Semantic search
        res = supabase.rpc("match_knowledge_chunks", {
            "query_embedding": query_embedding,
            "match_threshold": 0.3,
            "match_count": top_k
        }).execute()
        
        chunks = res.data or []
        
        # If vector search is weak, try keyword fallback
        if not chunks:
            res_kw = supabase.table("knowledge_chunks").select("*, knowledge_sources(title, source_type)").ilike("content", f"%{query}%").limit(top_k).execute()
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
                "similarity": c.get('similarity', 0),
                "content": c['content']
            })

        return {
            "context_text": "\n\n".join(context_parts),
            "chunks_used": chunks_metadata
        }
    except Exception as e:
        logger.error(f"RAG fetch error: {e}")
        return {"context_text": "", "chunks_used": []}

def log_message(session_uuid, role, content, input_source="system", metadata=None):
    """Saves a message to the conversation_messages table."""
    try:
        # Get next message index
        res = supabase.table("conversation_messages").select("message_index").eq("session_id", session_uuid).order("message_index", desc=True).limit(1).execute()
        next_idx = (res.data[0]['message_index'] + 1) if res.data else 1
        
        supabase.table("conversation_messages").insert({
            "session_id": session_uuid,
            "message_index": next_idx,
            "role": role,
            "content": content,
            "input_source": input_source,
            "metadata": metadata or {}
        }).execute()
        
        # Update session total count
        supabase.table("conversation_sessions").update({"total_messages": next_idx}).eq("id", session_uuid).execute()
    except Exception as e:
        logger.error(f"Logging error: {e}")

def get_or_create_session(session_id, topic):
    """Gets or creates a conversation session."""
    try:
        res = supabase.table("conversation_sessions").select("id").eq("session_id", session_id).execute()
        if res.data:
            return res.data[0]['id']
        
        new_res = supabase.table("conversation_sessions").insert({
            "session_id": session_id,
            "topic": topic,
            "status": "active"
        }).execute()
        return new_res.data[0]['id']
    except Exception as e:
        logger.error(f"Session creation error: {e}")
        return None

async def research_scan() -> dict:
    """Samples 3 representative chunks from each knowledge source."""
    try:
        sources = supabase.table("knowledge_sources").select("id, title, source_type").execute()
        briefing = []
        for s in sources.data:
            chunks = supabase.table("knowledge_chunks").select("content, location_marker").eq("source_id", s["id"]).limit(50).execute()
            if not chunks.data: continue
            
            total = len(chunks.data)
            indices = [0, total // 2, total - 1]
            for idx in set(indices): # set to avoid duplicates if total < 3
                if idx < total:
                    briefing.append({
                        "source_title": s["title"],
                        "source_type": s["source_type"],
                        "location_marker": chunks.data[idx]["location_marker"],
                        "content": chunks.data[idx]["content"]
                    })
        return {"briefing": briefing}
    except Exception as e:
        logger.error(f"Research scan error: {e}")
        return {"briefing": []}

# ============================================================
# DEEPGRAM STT ENDPOINT
# ============================================================

@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Accepts an audio file (webm/wav from browser MediaRecorder),
    sends it to Deepgram for speech-to-text transcription.
    """
    if not DEEPGRAM_API_KEY or DEEPGRAM_API_KEY.startswith("your-"):
        raise HTTPException(status_code=500, detail="Deepgram API key not configured. Add DEEPGRAM_API_KEY to .env")

    try:
        audio_bytes = await audio.read()
        content_type = audio.content_type or "audio/webm"
        logger.info(f"Received audio: {len(audio_bytes)} bytes, type: {content_type}")

        # Call Deepgram REST API
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=en",
                headers={
                    "Authorization": f"Token {DEEPGRAM_API_KEY}",
                    "Content-Type": content_type,
                },
                content=audio_bytes,
            )

        if resp.status_code != 200:
            logger.error(f"Deepgram error {resp.status_code}: {resp.text}")
            raise HTTPException(status_code=502, detail=f"Deepgram API error: {resp.status_code}")

        result = resp.json()
        transcript = (
            result.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
        )

        logger.info(f"Transcription result: {transcript[:100]}...")
        return {"transcript": transcript}

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Deepgram transcription timed out")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# AUDIT LOG ENDPOINTS
# ============================================================

@app.post("/audit-log")
async def save_audit_entry(entry: dict):
    """
    Saves a conversation entry to the in-memory audit log.
    Entry format: {session_id, role, text, timestamp}
    """
    session_id = entry.get("session_id", "default")
    if session_id not in audit_logs:
        audit_logs[session_id] = []

    log_entry = {
        "role": entry.get("role", "unknown"),
        "text": entry.get("text", ""),
        "timestamp": entry.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "source": entry.get("source", "text"),  # 'text' or 'voice'
    }
    audit_logs[session_id].append(log_entry)
    logger.info(f"Audit log [{session_id}]: {log_entry['role']} ({log_entry['source']}): {log_entry['text'][:60]}...")
    return {"status": "saved", "total_entries": len(audit_logs[session_id])}


@app.get("/audit-log/{session_id}")
async def get_audit_log(session_id: str):
    """Returns the full audit log for a given session."""
    entries = audit_logs.get(session_id, [])
    return {"session_id": session_id, "entries": entries, "total": len(entries)}


@app.get("/audit-log")
async def list_audit_sessions():
    """Lists all sessions with audit logs."""
    return {
        "sessions": [
            {"session_id": sid, "entries": len(entries)}
            for sid, entries in audit_logs.items()
        ]
    }


@app.post("/prepare-interview")
async def prepare_interview_endpoint(request: PrepareInterviewRequest):
    """
    Stage 1: Research Scan
    Stage 2: Theme Extraction
    Stage 3: Script Crafting
    """
    try:
        # 1. Research Scan
        research = await research_scan()
        briefing_text = json.dumps(research["briefing"])
        
        # 2. Theme Extraction
        theme_prompt = THEME_EXTRACTION_PROMPT.format(research_briefing=briefing_text)
        theme_res = llm.invoke(theme_prompt)
        
        try:
            cleaned_themes = theme_res.content.strip()
            if "```json" in cleaned_themes:
                cleaned_themes = cleaned_themes.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_themes:
                cleaned_themes = cleaned_themes.split("```")[1].split("```")[0].strip()
            themes_data = json.loads(cleaned_themes)
            # If LLM returned a list directly, wrap it
            if isinstance(themes_data, list):
                themes_data = {"themes": themes_data}
        except Exception as e:
            logger.warning(f"Theme parsing failed: {e}")
            themes_data = {"themes": []}
        
        # Extract themes list safely
        themes_list = themes_data.get("themes", []) if isinstance(themes_data, dict) else []
            
        # 3. Script Crafting
        script_prompt = SCRIPT_CRAFTING_PROMPT.format(
            themes_json=json.dumps(themes_data),
            research_briefing=briefing_text
        )
        script_res = llm.invoke(script_prompt)
        
        try:
            cleaned_script = script_res.content.strip()
            if "```json" in cleaned_script:
                cleaned_script = cleaned_script.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_script:
                cleaned_script = cleaned_script.split("```")[1].split("```")[0].strip()
            script_data = json.loads(cleaned_script)
            if not isinstance(script_data, dict):
                raise Exception(f"Script is not a dict, got {type(script_data)}")
        except Exception as e:
            logger.error(f"Script parsing error: {e}")
            logger.error(f"Raw script content: {script_res.content[:500]}")
            raise Exception(f"Failed to parse script JSON: {e}")

        # 4. NORMALIZE phase keys so frontend always finds them
        script_data = normalize_script_phases(script_data)
        logger.info(f"Normalized script phases: {list(script_data.get('interview_arc', {}).keys())}")

        # Count total questions across all phases
        total_qs = 0
        for phase_data in script_data.get("interview_arc", {}).values():
            if isinstance(phase_data, dict):
                total_qs += len(phase_data.get("questions", []))
        logger.info(f"Total questions generated: {total_qs}")

        # 5. Save to Database
        try:
            supabase.table("interview_scripts").delete().eq("session_id", request.session_id).execute()
            supabase.table("interview_scripts").insert({
                "session_id": request.session_id,
                "themes": themes_list,
                "full_script": script_data,
                "research_briefing": research["briefing"],
                "total_questions": total_qs,
                "questions_completed": 0,
                "status": "active"
            }).execute()
        except Exception as e:
            logger.warning(f"Could not save script to DB (table might be missing): {e}")

        return {
            "status": "ready",
            "themes": themes_data.get("themes", []),
            "script": script_data
        }
    except Exception as e:
        logger.error(f"Preparation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/interview-script/{session_id}")
async def get_interview_script(session_id: str):
    try:
        res = supabase.table("interview_scripts").select("*").eq("session_id", session_id).execute()
        if not res.data:
            return {"status": "not_found"}
        return {"status": "found", "script": res.data[0]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/generate-question")
async def generate_next_question_endpoint(request: InterviewRequest):
    try:
        session_id = request.user_session_id
        expert_answer = request.expert_answer.strip()
        input_source = request.input_source or "text"
        
        session_uuid = get_or_create_session(session_id, request.topic)

        # 1. Load Script State
        script = None
        try:
            res = supabase.table("interview_scripts").select("*").eq("session_id", session_id).execute()
            if res.data:
                script = res.data[0]
        except:
            pass

        # FIRST HOOK
        if not expert_answer:
            if script:
                # Use Q1 from script
                arc = script['full_script'].get('interview_arc', {})
                # Try new phase name then fallback to old one
                phase_1 = arc.get('phase_1_foundation') or arc.get('phase_1_warmup')
                q1 = phase_1.get('questions', [{}])[0] if phase_1 else {}
                ai_question = q1.get('question_text', "Tell me about your first enterprise deal.")
                log_message(session_uuid, "ai", ai_question, "system", {"phase": "foundation", "script_q_id": q1.get('question_id')})
                return {"question": ai_question, "script_active": True, "current_q_id": q1.get('question_id')}
            else:
                first_hook_prompt = f"{JOURNALIST_BASE_PERSONA}\n\nAsk a provocative opening question to start an interview about: {request.topic}"
                response = llm.invoke(first_hook_prompt)
                ai_question = response.content.strip()
                log_message(session_uuid, "ai", ai_question, "system")
                return {"question": ai_question, "script_active": False}

        # Log Expert Answer
        log_message(session_uuid, "expert", expert_answer, input_source)

        # 2. RETRIEVAL
        rag_result = hybrid_rag_fetch(expert_answer)
        db_context = rag_result["context_text"]
        chunks_used = rag_result["chunks_used"]

        # 3. SCRIPT-AWARE EVALUATION
        if script:
            full_script = script['full_script']
            # Collect all questions across canonical phases
            all_qs = []
            for p in ['phase_1_foundation', 'phase_2_tension', 'phase_3_tactical', 'phase_4_synthesis']:
                phase_data = full_script.get('interview_arc', {}).get(p)
                if phase_data and isinstance(phase_data, dict):
                    all_qs.extend(phase_data.get('questions', []))
            
            current_idx = script.get('questions_completed', 0) or 0
            if not all_qs:
                # Script exists but has no questions — fall back to reactive
                scenario = "Script has no questions. React naturally based on RAG context."
                eval_data = {"internal_monologue": "Reactive mode - empty script"}
            else:
                if current_idx >= len(all_qs):
                    current_idx = len(all_qs) - 1
                
                current_q = all_qs[current_idx]
                
                # Use Script-Aware Evaluation
                eval_prompt = SCRIPT_AWARE_EVALUATION_PROMPT.format(
                    current_script_question=current_q.get('question_text', ''),
                    expert_answer=expert_answer,
                    completed=current_idx,
                    total=len(all_qs),
                    tangent_turns_remaining=2
                )
                eval_res = llm.invoke(eval_prompt)
                
                # Default eval_data in case parsing fails or action is unknown
                eval_data = {"scripted_question_resolved": True, "next_action": "next_script_question"}
                
                try:
                    cleaned_eval = eval_res.content.strip()
                    if "```json" in cleaned_eval:
                        cleaned_eval = cleaned_eval.split("```json")[1].split("```")[0].strip()
                    elif "```" in cleaned_eval:
                        cleaned_eval = cleaned_eval.split("```")[1].split("```")[0].strip()
                    eval_json = json.loads(cleaned_eval)
                    action = eval_json.get('next_action', 'next_script_question')
                    logic = eval_json.get('internal_monologue', '')
                    
                    if action == "drill_down":
                        ai_question = eval_json.get('drill_down_prompt', "Can you go deeper into that specific moment?")
                        log_message(session_uuid, "ai", ai_question, "system", {"action": "drill_down", "logic": logic})
                        return {"question": ai_question, "chunks_used": chunks_used, "progress": f"{current_idx}/{len(all_qs)}", "internal_monologue": logic}

                    # Use the parsed eval_data for all other actions
                    eval_data = eval_json
                except Exception as e:
                    logger.warning(f"Eval parse failed: {e}")
                    eval_data = {"scripted_question_resolved": True, "next_action": "next_script_question"}

                # Update Script Progress
                if eval_data.get("scripted_question_resolved"):
                    new_idx = current_idx + 1
                    try:
                        supabase.table("interview_scripts").update({"questions_completed": new_idx}).eq("session_id", session_id).execute()
                    except: pass
                    
                # Determine Scenario
                if eval_data.get("next_action") == "follow_tangent":
                    scenario = f"FOLLOW TANGENT: {eval_data.get('tangent_detected', {}).get('topic')}. Logic: {eval_data.get('internal_monologue')}"
                elif eval_data.get("next_action") == "bridge_back_to_script":
                    scenario = f"BRIDGE BACK: {eval_data.get('bridge_suggestion')}. Next script topic: {all_qs[min(current_idx+1, len(all_qs)-1)].get('question_text')}"
                else:
                    next_q = all_qs[min(current_idx + (1 if eval_data.get('scripted_question_resolved') else 0), len(all_qs)-1)]
                    scenario = f"PROCEED TO SCRIPT: {next_q.get('question_text')}. Emotional target: {next_q.get('emotional_trigger')}"

        else:
            # Fallback to reactive logic if no script
            scenario = "No script found. React naturally based on RAG context."
            eval_data = {"internal_monologue": "Reactive mode"}

        # 5. GENERATION
        gen_prompt = GENERATION_PHASE_PROMPT.format(
            persona=JOURNALIST_BASE_PERSONA,
            scenario_instruction=scenario,
            expert_answer=expert_answer
        )
        
        final_response = llm.invoke(gen_prompt)
        ai_question = final_response.content.strip()
        
        # Build the full decision object for transparency
        current_q_text = ""
        script_progress = "Reactive"
        if script and all_qs:
            current_q_text = all_qs[min(current_idx, len(all_qs)-1)].get('question_text', '')
            script_progress = f"{script.get('questions_completed', 0)}/{len(all_qs)}"
        
        decision_log = {
            "action": eval_data.get("next_action", "unknown"),
            "answer_depth": eval_data.get("answer_depth", "unknown"),
            "scripted_question_resolved": eval_data.get("scripted_question_resolved", False),
            "current_script_question": current_q_text,
            "script_progress": script_progress,
            "tangent_detected": eval_data.get("tangent_detected", {"exists": False}),
            "internal_monologue": eval_data.get("internal_monologue", ""),
            "scenario_used": scenario,
            "rag_sources": [c.get("source_title", "Unknown") for c in chunks_used[:3]] if chunks_used else []
        }
        
        # Log AI Question with full decision metadata
        log_message(session_uuid, "ai", ai_question, "system", {
            "decision": decision_log,
            "chunks_used": chunks_used[:3],
            "scenario": scenario
        })

        return {
            "question": ai_question,
            "script_active": script is not None,
            "progress": script_progress,
            "chunks_used": chunks_used[:3],
            "decision": decision_log
        }
    except Exception as e:
        logger.error(f"Question generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
