import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { 
  Mic, MicOff, Send, BrainCircuit, ChevronRight, History, ShieldCheck, 
  CloudDownload, Link, Loader2, CheckCircle, Terminal, Activity, 
  FileText, Map, Compass, Play, BookOpen, Sparkles, Layers, Globe, Cpu, Eye, EyeOff, Database, GitBranch, Target, MessageSquare
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
  const [expandedThemes, setExpandedThemes] = useState<Set<number>>(new Set());
  const [expandedQuestions, setExpandedQuestions] = useState<Set<string>>(new Set());
  const [showFramework, setShowFramework] = useState(false);
  const [scriptProgress, setScriptProgress] = useState<string>('0/0');
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());

  const resetSession = () => {
    const newId = crypto.randomUUID();
    setSessionId(newId);
    setMessages([]);
    setScript(null);
    setThemes([]);
    setScriptProgress('0/0');
    setShowFramework(false);
    setExpandedThemes(new Set());
    setExpandedQuestions(new Set());
    setOpenDecisionId(null);
    setView('landing');
  };

  const downloadTranscript = () => {
    const header = `=== AI JOURNALIST — INTERVIEW TRANSCRIPT ===\nSession ID: ${sessionId}\nDate: ${new Date().toISOString().split('T')[0]}\nProgress: ${scriptProgress}\n${'='.repeat(50)}\n\n`;
    const body = messages.map((msg, i) => {
      const role = msg.role === 'expert' ? 'EXPERT' : 'AI JOURNALIST';
      const time = new Date(msg.timestamp).toLocaleTimeString();
      let entry = `[${time}] ${role}:\n${msg.text}\n`;
      if (msg.decision?.internal_monologue) {
        entry += `  >> Decision: ${msg.decision.internal_monologue}\n`;
      }
      return entry;
    }).join('\n---\n\n');
    const blob = new Blob([header + body], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `interview_${sessionId.slice(0, 8)}_${new Date().toISOString().split('T')[0]}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

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
          <button className="btn-ghost" onClick={resetSession}>+ New Session</button>
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
    const toggleTheme = (id: number) => {
      setExpandedThemes(prev => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id); else next.add(id);
        return next;
      });
    };
    const toggleQuestion = (id: string) => {
      setExpandedQuestions(prev => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id); else next.add(id);
        return next;
      });
    };

    const totalQuestions = Object.values(script?.interview_arc || {}).reduce(
      (sum: number, phase: any) => sum + (phase.questions?.length || 0), 0
    );

    return (
      <div className="script-page">
        <header className="script-header">
          <div className="script-header-left">
            <BrainCircuit size={22} style={{ color: 'var(--accent)' }} />
            <div><small>Research Complete</small><h1>Interview Blueprint</h1></div>
          </div>
          <div style={{display:'flex',gap:10,alignItems:'center'}}>
            <button className="btn-ghost" onClick={() => setShowFramework(!showFramework)}>
              <Cpu size={14} style={{marginRight:4,verticalAlign:-2}}/>{showFramework ? 'Hide' : 'Show'} Framework
            </button>
            <button className="btn-go-live" onClick={() => setView('interview')}>
              {messages.length > 0 ? 'Return to Interview' : 'Launch Interview'} <Play size={16} />
            </button>
          </div>
        </header>

        {showFramework && (
          <div className="framework-banner">
            <h3><Cpu size={16} /> Script Generation Framework</h3>
            <div className="framework-stages">
              <div className="framework-stage">
                <div className="framework-stage-num">1</div>
                <div><strong>Research Scan</strong><p>Sampled 3 chunks per source (start, middle, end) across all knowledge sources → ~33 representative chunks</p></div>
              </div>
              <div className="framework-stage">
                <div className="framework-stage-num">2</div>
                <div><strong>Theme Extraction (LLM Call #1)</strong><p>Identified {themes.length} editorially compelling themes, each with emotional anchors and source evidence</p></div>
              </div>
              <div className="framework-stage">
                <div className="framework-stage-num">3</div>
                <div><strong>Script Crafting (LLM Call #2)</strong><p>Generated {totalQuestions} questions across 4 phases. Each question is grounded in a specific knowledge chunk with editorial reasoning.</p></div>
              </div>
            </div>
            <div className="framework-decision">
              <Activity size={14} /> <strong>Why this count?</strong> Each question targets ~3 min of conversation. {totalQuestions} × 3 = {totalQuestions * 3} min — optimal extraction window before expert fatigue.
            </div>
          </div>
        )}

        <div className="script-body">
          <div className="script-layout">
            <aside className="script-sidebar">
              <div className="section-label"><div className="section-label-dot" /> Extracted Themes ({themes.length})</div>
              {themes.map((t: any) => {
                const isOpen = expandedThemes.has(t.theme_id);
                return (
                  <div key={t.theme_id} className={`theme-card ${isOpen ? 'theme-expanded' : ''}`}>
                    <h4>{t.theme_title}</h4>
                    <p>{t.editorial_rationale}</p>
                    <button className="theme-toggle" onClick={() => toggleTheme(t.theme_id)}>
                      <Eye size={11} /> {isOpen ? 'Hide' : 'Show'} Reasoning
                    </button>
                    {isOpen && (
                      <div className="theme-details">
                        {t.emotional_anchor && (
                          <div className="theme-detail-row">
                            <span className="theme-detail-label"><Target size={11} /> Emotional Anchor</span>
                            <span>{t.emotional_anchor}</span>
                          </div>
                        )}
                        {t.never_asked_angle && (
                          <div className="theme-detail-row">
                            <span className="theme-detail-label"><Sparkles size={11} /> Never-Asked Angle</span>
                            <span>{t.never_asked_angle}</span>
                          </div>
                        )}
                        {t.source_evidence?.length > 0 && (
                          <div className="theme-detail-row">
                            <span className="theme-detail-label"><Database size={11} /> Source Evidence</span>
                            <div className="theme-evidence-list">
                              {t.source_evidence.map((s: any, i: number) => (
                                <div key={i} className="evidence-chip">
                                  <strong>{s.source_title}</strong>
                                  <small>{s.chunk_preview}</small>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </aside>
            <div className="script-main">
              <div className="section-label"><div className="section-label-dot" /> Full Narrative Script ({totalQuestions} questions)</div>
              {Object.entries(script?.interview_arc || {}).map(([key, phase]: [string, any]) => (
                <div key={key} className="phase-block">
                  <div className="phase-header">
                    <h4>{key.replace('phase_', '').replace(/_/g, ' ')}</h4>
                    {phase.phase_goal && <small>{phase.phase_goal}</small>}
                  </div>
                  {phase.questions?.map((q: any) => {
                    const qId = q.question_id || `q-${Math.random()}`;
                    const isQOpen = expandedQuestions.has(qId);
                    return (
                      <div key={qId} className={`question-card ${isQOpen ? 'question-expanded' : ''}`}>
                        <div className="question-top-row">
                          <div className="question-id">{q.question_id}</div>
                          <div className="question-content"><p>"{q.question_text}"</p></div>
                        </div>
                        <button className="question-rationale-btn" onClick={() => toggleQuestion(qId)}>
                          <Eye size={11} /> {isQOpen ? 'Hide' : 'Why this question?'}
                        </button>
                        {isQOpen && (
                          <div className="question-rationale-panel">
                            {q.emotional_trigger && (
                              <div className="qr-item">
                                <span className="qr-label"><Target size={11} /> Emotional Trigger</span>
                                <span className="qr-value">{q.emotional_trigger}</span>
                              </div>
                            )}
                            {q.chunk_attribution && (
                              <>
                                <div className="qr-item">
                                  <span className="qr-label"><Database size={11} /> Source</span>
                                  <span className="qr-value">{q.chunk_attribution.source_title}</span>
                                </div>
                                {q.chunk_attribution.why_this_chunk && (
                                  <div className="qr-item qr-why">
                                    <span className="qr-label"><MessageSquare size={11} /> Editorial Reasoning</span>
                                    <p>{q.chunk_attribution.why_this_chunk}</p>
                                  </div>
                                )}
                                {q.chunk_attribution.chunk_content && (
                                  <div className="qr-item">
                                    <span className="qr-label"><FileText size={11} /> Chunk That Inspired This</span>
                                    <code className="qr-chunk">{q.chunk_attribution.chunk_content}</code>
                                  </div>
                                )}
                              </>
                            )}
                            {q.contingency && (
                              <div className="qr-item">
                                <span className="qr-label"><GitBranch size={11} /> Contingency (if short answer)</span>
                                <span className="qr-value qr-contingency">{q.contingency}</span>
                              </div>
                            )}
                            {q.estimated_minutes && (
                              <div className="qr-item">
                                <span className="qr-label"><Activity size={11} /> Estimated Time</span>
                                <span className="qr-value">~{q.estimated_minutes} min</span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
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
          <div className="chat-header-info">
            <h1>Live Interview</h1>
            <span style={{fontSize: '10px', color: '#64748b', fontFamily: 'monospace'}}>{sessionId.slice(0, 8)}</span>
          </div>
        </div>
        <div className="chat-header-right">
          <button className="btn-ghost" onClick={downloadTranscript} style={{marginRight: '8px'}}>
            <CloudDownload size={14} style={{marginRight: '4px', verticalAlign: '-2px'}}/> Download
          </button>
          <button className="btn-ghost" onClick={() => setView('script_preview')} style={{marginRight: '12px'}}>
            <FileText size={14} style={{marginRight: '4px', verticalAlign: '-2px'}}/> View Script
          </button>
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
