import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import {
  Mic, MicOff, Send, BrainCircuit, Database, ChevronLeft,
  ShieldCheck, CloudDownload, Link, Loader2, CheckCircle,
  Play, FileText, Sparkles, Layers, BookOpen, ArrowRight,
  Zap, Globe, Lock, Cpu, Eye, EyeOff, GitBranch, Target,
  Activity, MessageSquare
} from 'lucide-react';

interface Decision {
  action: string;
  answer_depth: string;
  scripted_question_resolved: boolean;
  current_script_question: string;
  script_progress: string;
  tangent_detected: { exists: boolean; topic?: string; worth_following?: boolean };
  internal_monologue: string;
  scenario_used: string;
  rag_sources: string[];
}

interface Message {
  id: string;
  role: 'expert' | 'ai';
  text: string;
  timestamp: number;
  chunks?: any[];
  progress?: string;
  decision?: Decision;
}

interface ScriptData {
  themes: any[];
  script: any;
}

const API = 'http://localhost:8001';

const App: React.FC = () => {
  const [view, setView] = useState<'landing' | 'interview' | 'ingest' | 'research' | 'script_preview'>('landing');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [ingestionStatus, setIngestionStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [ingestionResult, setIngestionResult] = useState('');
  const [scriptData, setScriptData] = useState<ScriptData | null>(null);
  const [researchStep, setResearchStep] = useState(0);
  const [expandedDecisions, setExpandedDecisions] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (view === 'interview' && messages.length === 0) handleSend('', 'text');
  }, [view]);

  const handlePrepareInterview = async () => {
    setView('research');
    setResearchStep(1);
    try {
      setTimeout(() => setResearchStep(2), 2500);
      setTimeout(() => setResearchStep(3), 5000);
      const res = await axios.post(`${API}/prepare-interview`, {
        session_id: 'demo-session-001',
        topic: 'Enterprise Pre-Sales, Solutions Architecture & Deal Strategy'
      });
      setScriptData(res.data);
      setResearchStep(4);
      setTimeout(() => setView('script_preview'), 1200);
    } catch (e) {
      console.error(e);
      setView('landing');
      alert('Failed to prepare. Ensure knowledge is ingested.');
    }
  };

  const handleSend = async (text: string, source = 'text') => {
    if (!text.trim() && messages.length > 0) return;
    if (text.trim()) {
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'expert', text, timestamp: Date.now() }]);
    }
    setInputText('');
    setIsLoading(true);
    try {
      const res = await axios.post(`${API}/generate-question`, {
        expert_answer: text, user_session_id: 'demo-session-001', input_source: source,
      });
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(), role: 'ai', text: res.data.question,
        timestamp: Date.now(), chunks: res.data.chunks_used, progress: res.data.progress,
        decision: res.data.decision
      }]);
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(), role: 'ai',
        text: 'Connection error with the Knowledge Hub. Please try again.', timestamp: Date.now()
      }]);
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
            const r = await axios.post(`${API}/transcribe`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
            if (r.data.transcript?.trim()) handleSend(r.data.transcript.trim(), 'voice');
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
      const res = await axios.post(`${API}/ingest-youtube`, { url: youtubeUrl });
      setIngestionStatus('success');
      setIngestionResult(res.data.message);
    } catch (e) { console.error(e); setIngestionStatus('error'); }
  };

  // ─── LANDING ──────────────────────────────────────────
  if (view === 'landing') {
    return (
      <div className="landing">
        <nav className="landing-nav">
          <div className="landing-logo">
            <div className="landing-logo-icon"><BrainCircuit size={20} /></div>
            AI Journalist
          </div>
          <div className="landing-nav-actions">
            <button className="btn-ghost" onClick={() => setView('ingest')}>
              <CloudDownload size={14} style={{ marginRight: 6, verticalAlign: -2 }} />Ingest Hub
            </button>
          </div>
        </nav>

        <div className="landing-hero">
          <div className="landing-badge">
            <Zap size={12} />Tacit Knowledge Extraction Engine
          </div>
          <h1 className="landing-title">Build Your<br />Digital Twin.</h1>
          <p className="landing-subtitle">
            We research your expertise, craft an interview script, and extract the unwritten rules of your career — all grounded in your own data.
          </p>
          <button className="btn-primary" onClick={handlePrepareInterview}>
            Start Research Phase <ArrowRight size={16} />
          </button>
        </div>

        <div className="landing-stats">
          <div className="stat-item"><label>Knowledge Chunks</label><span>1,643</span></div>
          <div className="stat-item"><label>Extraction Rate</label><span>94.2%</span></div>
          <div className="stat-item"><label>Twin Fidelity</label><span>High</span></div>
        </div>
      </div>
    );
  }

  // ─── RESEARCH SCAN ────────────────────────────────────
  if (view === 'research') {
    const steps = [
      { id: 1, icon: Database, label: 'Scanning Knowledge Hub', sub: '1,643 chunks mapped' },
      { id: 2, icon: Sparkles, label: 'Extracting Core Themes', sub: 'Identifying tacit patterns' },
      { id: 3, icon: FileText, label: 'Crafting Interview Script', sub: 'Foundation → Depth arc' },
    ];
    return (
      <div className="research-page">
        <div className="research-card">
          <h2>Editorial Research Scan</h2>
          <p>Synthesizing 20 years of expertise into an interview blueprint...</p>
          <div className="research-steps">
            {steps.map(s => (
              <div key={s.id} className={`research-step ${researchStep >= s.id ? 'active' : ''}`}>
                <div className="research-step-icon"><s.icon size={18} /></div>
                <div className="research-step-text">
                  <strong>{s.label}</strong>
                  <small>{s.sub}</small>
                </div>
                <div className="research-step-status">
                  {researchStep > s.id && <CheckCircle size={18} />}
                  {researchStep === s.id && <Loader2 size={18} className="spin" />}
                </div>
              </div>
            ))}
          </div>
          <div className="progress-bar">
            <div className="progress-bar-fill" style={{ width: `${(Math.min(researchStep, 3) / 3) * 100}%` }} />
          </div>
        </div>
      </div>
    );
  }

  // ─── SCRIPT PREVIEW ───────────────────────────────────
  if (view === 'script_preview') {
    const phases = [
      { key: 'phase_1_foundation', label: 'Foundation', icon: Globe },
      { key: 'phase_2_tension', label: 'Tension', icon: Zap },
      { key: 'phase_3_tactical', label: 'Tactical Playbook', icon: Cpu },
      { key: 'phase_4_synthesis', label: 'Synthesis', icon: Layers },
    ];

    return (
      <div className="script-page">
        <header className="script-header">
          <div className="script-header-left">
            <BrainCircuit size={22} style={{ color: 'var(--accent)' }} />
            <div>
              <small>Research Complete</small>
              <h1>Interview Blueprint</h1>
            </div>
          </div>
          <button className="btn-go-live" onClick={() => setView('interview')}>
            Launch Interview <Play size={16} />
          </button>
        </header>

        <div className="script-body">
          <div className="script-layout">
            {/* Sidebar: Themes */}
            <aside className="script-sidebar">
              <div className="section-label"><div className="section-label-dot" /> Extracted Themes</div>
              {scriptData?.themes.map((t: any) => (
                <div key={t.theme_id} className="theme-card">
                  <div className="theme-card-header">
                    <h4>{t.theme_title}</h4>
                    <span className="theme-card-id">#{t.theme_id}</span>
                  </div>
                  <p>{t.editorial_rationale}</p>
                  {t.emotional_anchor && (
                    <div className="theme-card-anchor"><Zap size={10} /> {t.emotional_anchor}</div>
                  )}
                </div>
              ))}
              <div className="info-box">
                <div className="info-box-header"><ShieldCheck size={14} /> Grounded Logic</div>
                <p>Every question below is anchored to a real knowledge chunk from your ingested data. Nothing is hallucinated.</p>
              </div>
            </aside>

            {/* Main: Full Script */}
            <div className="script-main">
              <div className="section-label"><div className="section-label-dot" /> Full Narrative Script</div>
              {phases.map((phase, pIdx) => {
                const arc = scriptData?.script?.interview_arc;
                const data = arc?.[phase.key];
                if (!data) return null;
                return (
                  <div key={phase.key} className="phase-block">
                    <div className="phase-header">
                      <div className="phase-number">{pIdx + 1}</div>
                      <h4>Phase {pIdx + 1}: {phase.label}</h4>
                      <span className="phase-count">{data.questions?.length || 0} Questions</span>
                    </div>
                    {data.questions?.map((q: any) => (
                      <div key={q.question_id} className="question-card">
                        <div className="question-id">{q.question_id}</div>
                        <div className="question-content">
                          <p>"{q.question_text}"</p>
                          <div className="question-meta">
                            {q.chunk_attribution?.source_title && (
                              <span><BookOpen size={11} /> {q.chunk_attribution.source_title}</span>
                            )}
                            {q.emotional_trigger && (
                              <span style={{ color: 'var(--accent)' }}><Sparkles size={11} /> {q.emotional_trigger}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ─── INGEST ───────────────────────────────────────────
  if (view === 'ingest') {
    return (
      <div className="ingest-page">
        <div style={{ width: '100%', maxWidth: 560 }}>
          <button className="back-link" onClick={() => setView('landing')}>
            <ChevronLeft size={14} /> Back to Dashboard
          </button>
          <div className="ingest-card">
            <div className="ingest-header">
              <div className="ingest-icon"><CloudDownload size={24} /></div>
              <div>
                <h2>Ingestion Hub</h2>
                <small>Feed the Knowledge Engine</small>
              </div>
            </div>
            <div className="input-group">
              <label>YouTube Source URL</label>
              <div className="input-wrapper">
                <Link size={16} className="input-icon" />
                <input
                  className="input-field"
                  type="text"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={youtubeUrl}
                  onChange={e => setYoutubeUrl(e.target.value)}
                />
              </div>
            </div>
            <button className="btn-full" onClick={handleIngest} disabled={ingestionStatus === 'loading'}>
              {ingestionStatus === 'loading'
                ? <><Loader2 size={18} className="spin" /> Processing...</>
                : 'Synchronize Knowledge'}
            </button>
            {ingestionStatus === 'success' && (
              <div className="success-banner">
                <CheckCircle size={20} />
                <div><h4>Sync Complete</h4><p>{ingestionResult}</p></div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ─── INTERVIEW CHAT ───────────────────────────────────
  const lastProgress = messages.filter(m => m.progress).pop()?.progress;

  return (
    <div className="chat-page">
      <header className="chat-header">
        <div className="chat-header-left">
          <button className="chat-logo-btn" onClick={() => setView('landing')}>
            <BrainCircuit size={18} />
          </button>
          <div className="chat-header-info">
            <h1>AI Journalist — Live Interview</h1>
            <div className="chat-header-status"><Lock size={10} /> Grounded Protocols Active</div>
          </div>
        </div>
        <div className="chat-header-right">
          {lastProgress && (
            <div className="progress-section">
              <label>Script Progress</label>
              <div className="progress-track">
                <div className="progress-track-bar">
                  <div className="progress-track-fill" style={{
                    width: `${(parseInt(lastProgress.split('/')[0]) / parseInt(lastProgress.split('/')[1])) * 100}%`
                  }} />
                </div>
                <span>{lastProgress}</span>
              </div>
            </div>
          )}
          <div className="session-badge">Session: Demo-001</div>
        </div>
      </header>

      <div className="chat-feed" ref={scrollRef}>
        {messages.map(msg => {
          const isExpanded = expandedDecisions.has(msg.id);
          const toggleDecision = () => {
            setExpandedDecisions(prev => {
              const next = new Set(prev);
              if (next.has(msg.id)) next.delete(msg.id); else next.add(msg.id);
              return next;
            });
          };
          const actionLabel: Record<string, { icon: string; color: string; label: string }> = {
            'next_script_question': { icon: '✅', color: '#22c55e', label: 'Resolved → Next Question' },
            'drill_down': { icon: '🔍', color: '#f59e0b', label: 'Drilling Deeper' },
            'follow_tangent': { icon: '🌀', color: '#a78bfa', label: 'Following Tangent' },
            'bridge_back_to_script': { icon: '🌉', color: '#38bdf8', label: 'Bridging Back to Script' },
            'unknown': { icon: '⚡', color: '#94a3b8', label: 'Initial Hook' },
          };
          const d = msg.decision;
          const action = d ? (actionLabel[d.action] || actionLabel['unknown']) : null;

          return (
            <div key={msg.id} className={`msg ${msg.role === 'expert' ? 'msg-expert' : 'msg-ai'}`}>
              <div className="msg-bubble">
                {msg.role === 'ai' && (
                  <div className="msg-label">
                    <span><ShieldCheck size={10} /> Grounded Follow-up</span>
                    {msg.chunks?.[0]?.source_title && (
                      <span className="msg-source"><Database size={10} /> {msg.chunks[0].source_title}</span>
                    )}
                  </div>
                )}
                <div className="msg-text">{msg.text}</div>
              </div>

              {msg.role === 'ai' && d && (
                <div className="decision-section">
                  <button className="decision-toggle" onClick={toggleDecision}>
                    {isExpanded ? <EyeOff size={12} /> : <Eye size={12} />}
                    <span>Decision Log</span>
                    {action && <span className="decision-badge" style={{ background: action.color + '22', color: action.color }}>{action.icon} {action.label}</span>}
                  </button>

                  {isExpanded && (
                    <div className="decision-panel">
                      <div className="decision-grid">
                        <div className="decision-item">
                          <div className="decision-item-label"><GitBranch size={12} /> Action</div>
                          <div className="decision-item-value" style={{ color: action?.color }}>{action?.icon} {action?.label}</div>
                        </div>
                        <div className="decision-item">
                          <div className="decision-item-label"><Activity size={12} /> Answer Depth</div>
                          <div className="decision-item-value">
                            <span className={`depth-tag depth-${d.answer_depth}`}>{d.answer_depth}</span>
                          </div>
                        </div>
                        <div className="decision-item">
                          <div className="decision-item-label"><Target size={12} /> Script Position</div>
                          <div className="decision-item-value">{d.script_progress}</div>
                        </div>
                        <div className="decision-item">
                          <div className="decision-item-label"><CheckCircle size={12} /> Question Resolved</div>
                          <div className="decision-item-value">{d.scripted_question_resolved ? '✅ Yes' : '❌ No'}</div>
                        </div>
                      </div>

                      {d.current_script_question && (
                        <div className="decision-script-q">
                          <div className="decision-item-label"><FileText size={12} /> Current Script Question</div>
                          <p>{d.current_script_question}</p>
                        </div>
                      )}

                      {d.internal_monologue && (
                        <div className="decision-monologue">
                          <div className="decision-item-label"><MessageSquare size={12} /> Internal Monologue</div>
                          <p>{d.internal_monologue}</p>
                        </div>
                      )}

                      {d.tangent_detected?.exists && (
                        <div className="decision-tangent">
                          <div className="decision-item-label">🌀 Tangent Detected</div>
                          <p>Topic: {d.tangent_detected.topic || 'N/A'} | Worth: {d.tangent_detected.worth_following ? 'Yes' : 'No'}</p>
                        </div>
                      )}

                      {d.rag_sources?.length > 0 && (
                        <div className="decision-rag">
                          <div className="decision-item-label"><Database size={12} /> RAG Sources</div>
                          <div className="decision-rag-tags">
                            {d.rag_sources.map((s, i) => <span key={i} className="rag-tag">{s}</span>)}
                          </div>
                        </div>
                      )}

                      <div className="decision-scenario">
                        <div className="decision-item-label"><Cpu size={12} /> Scenario Instruction</div>
                        <code>{d.scenario_used}</code>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {isLoading && (
          <div className="msg msg-ai">
            <div className="typing-indicator">
              <div className="typing-dots">
                <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
              </div>
              <span className="typing-text">Synthesizing...</span>
            </div>
          </div>
        )}
      </div>

      <div className="chat-input-bar">
        <div className="chat-input-wrapper">
          <button
            className={`mic-btn ${isRecording ? 'recording' : ''}`}
            onClick={toggleRecording}
            disabled={isTranscribing}
          >
            {isTranscribing ? <Loader2 size={20} className="spin" /> : isRecording ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
          <textarea
            className="chat-textarea"
            rows={1}
            placeholder={isRecording ? '🔴 Recording...' : isTranscribing ? 'Transcribing...' : 'Share your insight...'}
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(inputText); } }}
            disabled={isRecording || isTranscribing}
          />
          <button className="send-btn" onClick={() => handleSend(inputText)}>
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default App;
