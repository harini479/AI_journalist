import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { 
  Mic, MicOff, Send, BrainCircuit, ChevronRight, History, ShieldCheck, 
  CloudDownload, Link, Loader2, CheckCircle, Terminal, Activity, 
  FileText, Map, Compass, Play, BookOpen, Sparkles, Layers, Globe, Cpu, Eye, EyeOff
} from 'lucide-react';

interface Decision {
  action: string;
  internal_monologue: string;
  scripted_question_resolved?: boolean;
  tangent_detected?: {
    exists: boolean;
    topic: string | null;
  };
  bridge_suggestion?: string;
}

interface Message {
  id: string;
  role: 'expert' | 'ai';
  text: string;
  timestamp: number;
  decision?: Decision;
  script_progress?: string;
  chunks?: any[];
}

interface ScriptPhase {
  phase_goal: string;
  questions: any[];
}

interface InterviewScript {
  interview_arc: {
    phase_1_warmup: ScriptPhase;
    phase_2_deep_dives: ScriptPhase;
    phase_3_challenge: ScriptPhase;
    phase_4_synthesis: ScriptPhase;
  };
}

const API_BASE = 'http://localhost:8001';

const App: React.FC = () => {
  const [view, setView] = useState<'landing' | 'research' | 'script_preview' | 'interview' | 'ingest'>('landing');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [researchStep, setResearchStep] = useState(0);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [ingestionStatus, setIngestionStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [ingestionResult, setIngestionResult] = useState<string>('');
  const [script, setScript] = useState<InterviewScript | null>(null);
  const [themes, setThemes] = useState<any[]>([]);
  const [openDecisionId, setOpenDecisionId] = useState<string | null>(null);
  const [scriptProgress, setScriptProgress] = useState<string>('0/0');
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const sessionId = 'demo-session-002';

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, openDecisionId]);

  useEffect(() => {
    if (view === 'interview' && messages.length === 0) handleSend('');
  }, [view]);

  const handlePrepareInterview = async () => {
    setView('research');
    setResearchStep(1);
    try {
      setTimeout(() => setResearchStep(2), 2000);
      setTimeout(() => setResearchStep(3), 4000);
      const response = await axios.post(`${API_BASE}/prepare-interview`, {
        user_session_id: sessionId,
        topic: "Technical Scaling in SaaS"
      });
      setScript(response.data.script);
      setThemes(response.data.themes);
      setResearchStep(4);
      setTimeout(() => setView('script_preview'), 1000);
    } catch (error) {
      console.error("Preparation error:", error);
      setView('landing');
    }
  };

  const handleSend = async (text: string) => {
    if (!text.trim() && messages.length > 0) return;
    if (text.trim()) {
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'expert', text, timestamp: Date.now() }]);
    }
    setInputText('');
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_BASE}/generate-question`, {
        expert_answer: text,
        user_session_id: sessionId
      });
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        text: response.data.question,
        timestamp: Date.now(),
        decision: response.data.decision,
        script_progress: response.data.script_progress,
        chunks: response.data.chunks_used
      }]);
      setScriptProgress(response.data.script_progress || 'Reactive');
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'ai', text: "Error connecting to Knowledge Hub.", timestamp: Date.now() }]);
    } finally { setIsLoading(false); }
  };

  const toggleRecording = async () => {
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        mediaRecorderRef.current = rec;
        audioChunksRef.current = [];
        rec.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
        rec.onstop = async () => {
          stream.getTracks().forEach(t => t.stop());
          const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          if (blob.size < 1000) return;
          setIsTranscribing(true);
          try {
            const fd = new FormData();
            fd.append('audio', blob, 'recording.webm');
            const r = await axios.post(`${API_BASE}/transcribe`, fd);
            if (r.data.transcript?.trim()) handleSend(r.data.transcript.trim());
          } catch (err) { console.error(err); }
          finally { setIsTranscribing(false); }
        };
        rec.start();
        setIsRecording(true);
      } catch (err) { console.error(err); }
    } else {
      if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current?.stop();
      setIsRecording(false);
    }
  };

  const handleIngest = async () => {
    if (!youtubeUrl.trim()) return;
    setIngestionStatus('loading');
    try {
      const res = await axios.post(`${API_BASE}/ingest-youtube`, { url: youtubeUrl });
      setIngestionStatus('success');
      setIngestionResult(res.data.message);
    } catch (e) { setIngestionStatus('error'); }
  };

  if (view === 'landing') {
    return (
      <div className="landing">
        <nav className="landing-nav">
          <div className="landing-logo">
            <div className="landing-logo-icon"><BrainCircuit size={20} /></div>
            AI Journalist
          </div>
          <button className="btn-ghost" onClick={() => setView('ingest')}>Ingest Hub</button>
        </nav>
        <div className="landing-hero">
          <div className="landing-badge"><Sparkles size={12} /> Extraction Engine Active</div>
          <h1 className="landing-title">Extract the<br />Unwritten Rules.</h1>
          <p className="landing-subtitle">Synthesizing expert tacit knowledge into structured intelligence.</p>
          <button className="btn-primary" onClick={handlePrepareInterview}>
            Initialize Interview <ChevronRight size={16} />
          </button>
        </div>
      </div>
    );
  }

  if (view === 'research') {
    const steps = [
      { id: 1, icon: Database, label: 'Scanning Knowledge Hub' },
      { id: 2, icon: Sparkles, label: 'Extracting Core Themes' },
      { id: 3, icon: FileText, label: 'Crafting Interview Script' },
    ];
    return (
      <div className="research-page">
        <div className="research-card">
          <h2>Editorial Research Scan</h2>
          <div className="research-steps">
            {steps.map(s => (
              <div key={s.id} className={`research-step ${researchStep >= s.id ? 'active' : ''}`}>
                <div className="research-step-icon"><s.icon size={18} /></div>
                <div className="research-step-text"><strong>{s.label}</strong></div>
                <div className="research-step-status">
                  {researchStep > s.id ? <CheckCircle size={18} /> : (researchStep === s.id && <Loader2 size={18} className="spin" />)}
                </div>
              </div>
            ))}
          </div>
          <div className="progress-bar"><div className="progress-bar-fill" style={{ width: `${(Math.min(researchStep, 3) / 3) * 100}%` }} /></div>
        </div>
      </div>
    );
  }

  if (view === 'script_preview') {
    return (
      <div className="script-page">
        <header className="script-header">
          <div className="script-header-left">
            <BrainCircuit size={22} style={{ color: 'var(--accent)' }} />
            <div><small>Research Complete</small><h1>Interview Blueprint</h1></div>
          </div>
          <button className="btn-go-live" onClick={() => setView('interview')}>Launch Interview <Play size={16} /></button>
        </header>
        <div className="script-body">
          <div className="script-layout">
            <aside className="script-sidebar">
              <div className="section-label"><div className="section-label-dot" /> Extracted Themes</div>
              {themes.map((t: any) => (
                <div key={t.theme_id} className="theme-card">
                  <h4>{t.theme_title}</h4>
                  <p>{t.editorial_rationale}</p>
                </div>
              ))}
            </aside>
            <div className="script-main">
              <div className="section-label"><div className="section-label-dot" /> Full Narrative Script</div>
              {Object.entries(script?.interview_arc || {}).map(([key, phase]: [string, any]) => (
                <div key={key} className="phase-block">
                  <div className="phase-header"><h4>{key.replace('phase_', '').replace('_', ' ')}</h4></div>
                  {phase.questions.map((q: any) => (
                    <div key={q.question_id} className="question-card">
                      <div className="question-id">{q.question_id}</div>
                      <div className="question-content"><p>"{q.question_text}"</p></div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (view === 'ingest') {
    return (
      <div className="ingest-page">
        <div className="ingest-card">
          <button className="back-link" onClick={() => setView('landing')}><ChevronRight size={14} style={{transform: 'rotate(180deg)'}} /> Back</button>
          <h2>Ingestion Hub</h2>
          <div className="input-group">
            <label>YouTube Source URL</label>
            <input className="input-field" type="text" value={youtubeUrl} onChange={e => setYoutubeUrl(e.target.value)} />
          </div>
          <button className="btn-full" onClick={handleIngest} disabled={ingestionStatus === 'loading'}>
            {ingestionStatus === 'loading' ? 'Processing...' : 'Synchronize Knowledge'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-page">
      <header className="chat-header">
        <div className="chat-header-left">
          <button className="chat-logo-btn" onClick={() => setView('landing')}><BrainCircuit size={18} /></button>
          <div className="chat-header-info"><h1>Live Interview</h1></div>
        </div>
        <div className="chat-header-right">
          <div className="progress-section"><label>Progress</label><span>{scriptProgress}</span></div>
        </div>
      </header>

      <div className="chat-feed" ref={scrollRef}>
        {messages.map(msg => (
          <div key={msg.id} className={`msg ${msg.role === 'expert' ? 'msg-expert' : 'msg-ai'}`}>
            <div className="msg-bubble">
              {msg.role === 'ai' && <div className="msg-label"><span><ShieldCheck size={10} /> Grounded Follow-up</span></div>}
              <div className="msg-text">{msg.text}</div>
            </div>
            {msg.role === 'ai' && msg.decision && (
              <div className="decision-section">
                <button className="decision-toggle" onClick={() => setOpenDecisionId(openDecisionId === msg.id ? null : msg.id)}>
                  <Activity size={12} /> Decision Log
                </button>
                {openDecisionId === msg.id && (
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl mt-2 text-xs">
                    <p className="text-indigo-400 font-bold mb-2">Internal Monologue:</p>
                    <p className="text-slate-300 italic mb-3">"{msg.decision.internal_monologue}"</p>
                    {msg.chunks && msg.chunks.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-800">
                        <p className="text-emerald-500 font-bold mb-1">Source Context:</p>
                        <p className="text-slate-500">{msg.chunks[0].source_title}: {msg.chunks[0].content}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {isLoading && <div className="typing-indicator"><div className="typing-dots"><div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" /></div></div>}
      </div>

      <footer className="chat-input-bar">
        <div className="chat-input-wrapper">
          <button className={`mic-btn ${isRecording ? 'recording' : ''}`} onClick={toggleRecording}>
            {isRecording ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
          <input className="chat-textarea" placeholder="Speak or type your insight..." value={inputText} onChange={e => setInputText(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSend(inputText)} />
          <button className="send-btn" onClick={() => handleSend(inputText)}><Send size={20} /></button>
        </div>
      </footer>
    </div>
  );
};

export default App;
