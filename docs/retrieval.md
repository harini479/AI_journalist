# **Technical Specification: Agentic Memory & Backlog Management System**

## **1. Executive Summary**
The Agentic Memory System upgrades the AI Journalist from a simple reactive chatbot into an intelligent, state-aware interviewer. Instead of forcing backlogged questions sequentially or dropping them entirely, the system maintains a dynamic "Question Backlog." It actively listens to the expert's ongoing answers to self-prune questions that get resolved naturally and waits for the perfect conceptual bridge to ask remaining questions. 

This ensures a hyper-organic conversational flow, zero redundancy, and a high-fidelity thought-leadership persona.

## **2. Core Operational Logic**

The system relies on two primary mechanics to manage the interview state without breaking the conversational illusion:

### **2.1 Organic Self-Pruning**
Experts frequently answer multiple unasked questions within a single, long-form response. The AI Journalist evaluates every new expert answer against the current Question Backlog. If the expert's monologue naturally addresses a queued topic, the system automatically deletes that question from the backlog. This guarantees the AI never asks a redundant question.

### **2.2 Contextual Syncing & Bridging**
Backlogged questions are held in a dormant state until a "perfect sync" occurs. A sync is defined as a moment where the current conversational thread naturally brushes up against a backlogged topic. When this happens, the AI Journalist generates a "Conversational Bridge" (e.g., *"That ties perfectly into something we touched on earlier..."*) to smoothly pivot the interview to the backlogged question.

---

## **3. Architecture & State Management**

The workflow requires the FastAPI backend to intercept the LLM process, splitting it into an **Evaluation Phase** and a **Generation Phase**. 

### **3.1 Database Schema Update (Supabase)**
A new state array must be added to track the dynamic backlog per session.

```sql
-- Track the active backlog for a specific interview session
CREATE TABLE interview_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_name VARCHAR(255),
    question_backlog JSONB DEFAULT '[]'::jsonb, -- Stores the array of pending gaps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### **3.2 Execution Workflow (Python / FastAPI)**

1. **Input Reception:** The React.js frontend sends the latest transcribed `expert_answer` to the Python backend.
2. **Context Retrieval:** The pure Python retrieval pipeline fetches new context from the Hybrid RAG database based on the expert's answer.
3. **Database Read:** The backend queries Supabase for the current `question_backlog` array.
4. **The Evaluation Phase:** The backend sends the answer, new context, and backlog to the LLM, strictly requesting a JSON response to assess the state of the interview.
5. **State Update:** The backend parses the JSON. It deletes pruned questions from Supabase and appends any newly discovered gaps.
6. **The Generation Phase:** The backend triggers a final LLM call to formulate the exact output question (either a new gap or a synced backlog question) and streams it back to the React UI.

---

## **4. Prompt Engineering Implementation**

To execute this without overwhelming the context window or causing the LLM to hallucinate instructions, the prompt architecture utilizes a structured JSON schema.

### **Phase 1: The Internal Monologue Prompt (Evaluation)**
This prompt does not generate the final question. It only analyzes the state of the interview.

```python
def build_evaluation_prompt(expert_answer, retrieved_context, current_backlog):
    return f"""
    You are the logic engine for an expert AI Journalist. Analyze the data below and output a STRICT JSON object.
    
    EXPERT ANSWER: {expert_answer}
    NEW CONTEXT: {retrieved_context}
    CURRENT BACKLOG: {current_backlog}
    
    Return a JSON object matching this exact schema:
    {{
      "pruned_questions": [
         // Array of exact strings from the CURRENT BACKLOG that the expert just answered. If none, return [].
      ],
      "new_gaps_found": [
         // Array of strings detailing any NEW conceptual gaps found between the EXPERT ANSWER and NEW CONTEXT. If none, return [].
      ],
      "sync_found": {{
         "is_synced": boolean, // True if the EXPERT ANSWER naturally connects to a remaining BACKLOG question.
         "target_backlog_question": "string" // The specific backlog question that syncs perfectly. (Leave empty if false).
      }}
    }}
    """
```

### **Phase 2: The Generation Prompt**
Once the FastAPI backend updates the database based on Phase 1, it determines the final instruction for the AI Journalist.

**Condition A: `is_synced` == True**
> "The expert just answered: `{expert_answer}`. Smoothly bridge this answer to the following backlogged topic: `{target_backlog_question}`. Ensure the transition sounds natural and professional."

**Condition B: `is_synced` == False**
> "Synthesize the `{expert_answer}` with the `{retrieved_context}`. Formulate ONE highly targeted follow-up question based on the newly discovered gap: `{new_gaps_found[0]}`. Do not use transitional phrasing."

---

## **5. Technical Considerations & Trade-offs**

*   **Latency Overhead:** Because this requires two distinct LLM calls per turn (Evaluation -> Generation), backend latency will slightly increase. Utilizing highly optimized models (like Gemini Flash) for the JSON Evaluation Phase can keep this under the 3-second UI threshold.
*   **Token Optimization:** To prevent context window bloat, the Python backend must strictly enforce a maximum limit on the `question_backlog` array (e.g., maximum of 5 stored gaps). If a 6th gap is found, the system should silently drop the oldest, least relevant gap in the database.