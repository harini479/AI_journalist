import requests
import json

BASE_URL = "http://localhost:9120"

def test_interview_loop():
    print("--- TESTING AGENTIC INTERVIEW LOOP ---")
    
    # 1. Start Interview (First Hook)
    print("\n[Phase 1] Triggering First Hook...")
    payload = {
        "expert_answer": "",
        "user_session_id": "test-session-123",
        "topic": "Enterprise Pre-Sales, Solutions Architecture & Deal Strategy"
    }
    res = requests.post(f"{BASE_URL}/generate-question", json=payload)
    data = res.json()
    first_question = data.get('question')
    print(f"AI Journalist: {first_question}")
    
    # 2. Simulate Expert Answer
    print("\n[Phase 2] Sending Expert Answer...")
    payload = {
        "expert_answer": "I believe AI will revolutionize healthcare primarily through predictive diagnostics, but the scaling of these systems requires a more robust ethical framework than what we currently have.",
        "user_session_id": "test-session-123"
    }
    res = requests.post(f"{BASE_URL}/generate-question", json=payload)
    data = res.json()
    
    print("\n--- AGENTIC LOGIC ---")
    print(f"Backlog Status: {json.dumps(data.get('backlog'), indent=2)}")
    print(f"Internal Logic (Monologue): {json.dumps(data.get('internal_logic'), indent=2)}")
    print(f"\nAI Journalist (Bridged Question): {data.get('question')}")

if __name__ == "__main__":
    test_interview_loop()
