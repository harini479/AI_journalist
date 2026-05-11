import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import {
  Mic, MicOff, Send, BrainCircuit, ChevronRight, ShieldCheck,
  CloudDownload, Loader2, CheckCircle, Activity,
  FileText, Play, Sparkles, Cpu, Eye, Database, GitBranch, Target, MessageSquare,
  Upload, Trash2, AlertCircle, FolderOpen, Zap, BookOpen, Lightbulb, Crosshair,
  Swords, Route, HelpCircle, BarChart3, StopCircle
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

const API_BASE = import.meta.env.VITE_API_BASE || `http://${window.location.hostname}:8001`;

const App: React.FC = () => {
  const [view, setView] = useState<'landing' | 'research' | 'script_preview' | 'interview' | 'ingest' | 'report'>('landing');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [_isTranscribing, setIsTranscribing] = useState(false);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [researchStep, setResearchStep] = useState(0);
  const [ingestionStatus, setIngestionStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState<{filename: string; status: string; chunks?: number}[]>([]);
  const [knowledgeSources, setKnowledgeSources] = useState<any[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [script, setScript] = useState<InterviewScript | null>(null);
  const [themes, setThemes] = useState<any[]>([]);
  const [openDecisionId, setOpenDecisionId] = useState<string | null>(null);
  const [expandedThemes, setExpandedThemes] = useState<Set<number>>(new Set());
  const [expandedQuestions, setExpandedQuestions] = useState<Set<string>>(new Set());
  const [showFramework, setShowFramework] = useState(false);
  const [scriptProgress, setScriptProgress] = useState<string>('0/0');
  const [knowledgeReport, setKnowledgeReport] = useState<any>(null);
  const [isSynthesizing, setIsSynthesizing] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const generateSessionId = () => {
    if (window.crypto?.randomUUID) {
      return window.crypto.randomUUID();
    }

    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  };

  const [sessionId, setSessionId] = useState(() => generateSessionId());

  const resetSession = () => {
    const newId = generateSessionId();
    setSessionId(newId);
    setMessages([]);
    setScript(null);
    setThemes([]);
    setScriptProgress('0/0');
    setShowFramework(false);
    setExpandedThemes(new Set());
    setExpandedQuestions(new Set());
    setOpenDecisionId(null);
    setKnowledgeReport(null);
    setView('landing');
  };

  const handleSynthesizeKnowledge = async () => {
    setIsSynthesizing(true);
    try {
      const res = await axios.post(`${API_BASE}/synthesize-knowledge/${sessionId}`, {}, { timeout: 300000 });
      if (res.data.status === 'success') {
        setKnowledgeReport(res.data.report);
        setView('report');
      } else {
        alert('Synthesis failed: ' + (res.data.message || 'Unknown error'));
      }
    } catch (e: any) {
      console.error('Synthesis error:', e);
      alert('Failed to synthesize knowledge: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleEndInterview = async () => {
    if (!confirm('End the interview now? This will stop the session and extract tacit knowledge from what has been covered so far.')) return;
    setIsSynthesizing(true);
    try {
      const res = await axios.post(`${API_BASE}/end-interview/${sessionId}`, {}, { timeout: 300000 });
      if (res.data.report) {
        setKnowledgeReport(res.data.report);
        setView('report');
      } else {
        alert(res.data.message || 'Interview ended.');
        setView('landing');
      }
    } catch (e: any) {
      console.error('End interview error:', e);
      alert('Failed to end interview: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsSynthesizing(false);
    }
  };

  const downloadTranscript = () => {
    const header = `=== AI JOURNALIST — INTERVIEW TRANSCRIPT ===\nSession ID: ${sessionId}\nDate: ${new Date().toISOString().split('T')[0]}\nProgress: ${scriptProgress}\n${'='.repeat(50)}\n\n`;
    const body = messages.map((msg) => {
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
      }, { timeout: 120000 });
      setScript(response.data.script);
      setThemes(response.data.themes);
      setResearchStep(4);
      setTimeout(() => setView('script_preview'), 1000);
    } catch (error: any) {
      console.error("Preparation error:", error);
      const detail = error?.response?.data?.detail || error?.message || 'Unknown error';
      alert(`Interview preparation failed: ${detail}\n\nPlease make sure the backend server is running on port 8001 and try again.`);
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



  const loadKnowledgeSources = async () => {
    setSourcesLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/knowledge-sources`);
      setKnowledgeSources(res.data.sources || []);
    } catch (e) { console.error('Failed to load sources:', e); }
    finally { setSourcesLoading(false); }
  };

  const handleFileUpload = async () => {
    if (uploadFiles.length === 0) return;
    setIngestionStatus('loading');
    setUploadProgress([]);
    try {
      const formData = new FormData();
      uploadFiles.forEach(f => formData.append('files', f));
      const res = await axios.post(`${API_BASE}/ingest-documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      });
      setUploadProgress(res.data.results || []);
      setIngestionStatus('success');
      setUploadFiles([]);
      loadKnowledgeSources();
    } catch (e: any) {
      console.error('Upload error:', e);
      setIngestionStatus('error');
      setUploadProgress([{ filename: 'Upload', status: 'error', chunks: 0 }]);
    }
  };

  const handleDeleteSource = async (sourceId: string) => {
    if (!confirm('Delete this source and all its chunks?')) return;
    try {
      await axios.delete(`${API_BASE}/knowledge-sources/${sourceId}`);
      loadKnowledgeSources();
    } catch (e) { console.error('Delete error:', e); }
  };

  const handleDeleteAllSources = async () => {
    if (!confirm('Delete ALL knowledge sources? This cannot be undone.')) return;
    try {
      await axios.delete(`${API_BASE}/knowledge-sources`);
      setKnowledgeSources([]);
    } catch (e) { console.error('Delete all error:', e); }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files).filter(f =>
      f.name.endsWith('.docx') || f.name.endsWith('.pdf') || f.name.endsWith('.txt')
    );
    setUploadFiles(prev => [...prev, ...files]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setUploadFiles(prev => [...prev, ...Array.from(e.target.files!)]);
    }
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
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="btn-ghost" onClick={() => setShowFramework(!showFramework)}>
              <Cpu size={14} style={{ marginRight: 4, verticalAlign: -2 }} />{showFramework ? 'Hide' : 'Show'} Framework
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
    // Load sources on first render of ingest view
    if (knowledgeSources.length === 0 && !sourcesLoading) {
      loadKnowledgeSources();
    }
    return (
      <div className="ingest-page">
        <div className="ingest-container">
          <button className="back-link" onClick={() => setView('landing')}>
            <ChevronRight size={14} style={{ transform: 'rotate(180deg)' }} /> Back to Home
          </button>
          <h2 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '4px' }}>
            <Database size={20} style={{ verticalAlign: '-3px', marginRight: '8px', color: '#818cf8' }} />
            Knowledge Hub
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '24px' }}>Upload documents to build your interview knowledge base</p>

          {/* File Upload Area */}
          <div
            className="upload-dropzone"
            onDragOver={e => e.preventDefault()}
            onDrop={handleFileDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".docx,.pdf,.txt"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            <Upload size={32} style={{ color: '#818cf8', marginBottom: '12px' }} />
            <p style={{ fontWeight: 600, fontSize: '15px', marginBottom: '4px' }}>Drop files here or click to browse</p>
            <p style={{ color: '#64748b', fontSize: '12px' }}>Supports: DOCX, PDF, TXT</p>
          </div>

          {/* Selected Files List */}
          {uploadFiles.length > 0 && (
            <div className="upload-file-list">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '13px', fontWeight: 600 }}>{uploadFiles.length} file{uploadFiles.length > 1 ? 's' : ''} selected</span>
                <button className="btn-ghost" style={{ fontSize: '11px', padding: '4px 8px' }} onClick={() => setUploadFiles([])}>Clear All</button>
              </div>
              {uploadFiles.map((f, i) => (
                <div key={i} className="upload-file-item">
                  <FileText size={14} style={{ color: '#818cf8', flexShrink: 0 }} />
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                  <span style={{ color: '#64748b', fontSize: '11px', flexShrink: 0 }}>{(f.size / 1024).toFixed(0)} KB</span>
                  <button style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px' }}
                    onClick={(e) => { e.stopPropagation(); setUploadFiles(prev => prev.filter((_, idx) => idx !== i)); }}>
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              <button
                className="btn-primary"
                style={{ width: '100%', marginTop: '12px', justifyContent: 'center' }}
                onClick={handleFileUpload}
                disabled={ingestionStatus === 'loading'}
              >
                {ingestionStatus === 'loading' ? (
                  <><Loader2 size={14} className="spin" /> Ingesting...</>
                ) : (
                  <><Upload size={14} /> Ingest {uploadFiles.length} File{uploadFiles.length > 1 ? 's' : ''}</>
                )}
              </button>
            </div>
          )}

          {/* Upload Results */}
          {uploadProgress.length > 0 && (
            <div className="upload-results">
              <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>Ingestion Results</h3>
              {uploadProgress.map((r, i) => (
                <div key={i} className={`upload-result-item ${r.status}`}>
                  {r.status === 'success' ? <CheckCircle size={14} style={{ color: '#22c55e' }} /> :
                   r.status === 'error' ? <AlertCircle size={14} style={{ color: '#ef4444' }} /> :
                   <Loader2 size={14} className="spin" />}
                  <span style={{ flex: 1 }}>{r.filename}</span>
                  <span style={{ color: '#64748b', fontSize: '11px' }}>
                    {r.status === 'success' ? `${r.chunks} chunks` : r.status}
                  </span>
                </div>
              ))}
            </div>
          )}


          {/* Existing Knowledge Sources */}
          <div style={{ marginTop: '32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600 }}>
                <FolderOpen size={14} style={{ verticalAlign: '-2px', marginRight: '6px', color: '#818cf8' }} />
                Knowledge Sources ({knowledgeSources.length})
              </h3>
              {knowledgeSources.length > 0 && (
                <button className="btn-ghost" style={{ fontSize: '11px', color: '#ef4444', padding: '4px 8px' }} onClick={handleDeleteAllSources}>
                  <Trash2 size={11} style={{ marginRight: '4px' }} /> Clear All
                </button>
              )}
            </div>
            {sourcesLoading ? (
              <div style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}><Loader2 size={18} className="spin" /></div>
            ) : knowledgeSources.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '32px', color: '#475569', fontSize: '13px', border: '1px dashed #1e293b', borderRadius: '12px' }}>
                No sources ingested yet. Upload documents above to get started.
              </div>
            ) : (
              <div className="sources-list">
                {knowledgeSources.map(s => (
                  <div key={s.id} className="source-item">
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 500, fontSize: '13px' }}>{s.title}</div>
                      <div style={{ color: '#64748b', fontSize: '11px', marginTop: '2px' }}>
                        {s.source_type} · {s.chunk_count} chunks · {new Date(s.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <button
                      style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px' }}
                      onClick={() => handleDeleteSource(s.id)}
                      title="Delete source"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ======= TACIT KNOWLEDGE REPORT VIEW =======
  if (view === 'report' && knowledgeReport) {
    const r = knowledgeReport;
    return (
      <div className="report-page">
        <div className="report-container">
          <button className="back-link" onClick={() => setView('interview')}>
            <ChevronRight size={14} style={{ transform: 'rotate(180deg)' }} /> Back to Interview
          </button>

          {/* Report Header */}
          <div className="report-header">
            <div className="report-badge"><Zap size={12} /> TACIT KNOWLEDGE REPORT</div>
            <h1 className="report-title">{r.report_title || 'Knowledge Report'}</h1>
            <p className="report-domain">{r.expert_domain}</p>
            <div className="report-stats">
              <div className="report-stat">
                <BarChart3 size={16} />
                <div>
                  <span className="stat-number">{r.interview_depth_score}/10</span>
                  <span className="stat-label">Depth Score</span>
                </div>
              </div>
              <div className="report-stat">
                <Lightbulb size={16} />
                <div>
                  <span className="stat-number">{r.total_insights_extracted}</span>
                  <span className="stat-label">Insights</span>
                </div>
              </div>
              <div className="report-stat">
                <BookOpen size={16} />
                <div>
                  <span className="stat-number">{r.war_stories?.length || 0}</span>
                  <span className="stat-label">War Stories</span>
                </div>
              </div>
              <div className="report-stat">
                <Route size={16} />
                <div>
                  <span className="stat-number">{r.actionable_playbooks?.length || 0}</span>
                  <span className="stat-label">Playbooks</span>
                </div>
              </div>
            </div>
            <p className="report-summary">{r.summary}</p>
          </div>

          {/* Tacit Insights */}
          {r.tacit_insights?.length > 0 && (
            <div className="report-section">
              <h2 className="section-title"><Lightbulb size={18} /> Tacit Insights</h2>
              <div className="report-cards">
                {r.tacit_insights.map((item: any) => (
                  <div key={item.id} className="report-card insight-card">
                    <div className="card-header">
                      <span className={`confidence-badge ${item.confidence?.toLowerCase()}`}>{item.confidence}</span>
                      <span className="card-theme">{item.theme}</span>
                    </div>
                    <p className="card-insight">{item.insight}</p>
                    <p className="card-why"><strong>Why tacit:</strong> {item.why_tacit}</p>
                    <blockquote className="card-quote">"{item.expert_quote}"</blockquote>
                    <p className="card-source">Triggered by: {item.source_question}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Mental Models */}
          {r.mental_models?.length > 0 && (
            <div className="report-section">
              <h2 className="section-title"><Cpu size={18} /> Mental Models</h2>
              <div className="report-cards">
                {r.mental_models.map((item: any) => (
                  <div key={item.id} className="report-card model-card">
                    <h3 className="model-name">{item.model_name}</h3>
                    <p className="card-desc">{item.description}</p>
                    <p className="card-application"><strong>Application:</strong> {item.application}</p>
                    <blockquote className="card-quote">"{item.expert_quote}"</blockquote>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Pattern Breaks */}
          {r.pattern_breaks?.length > 0 && (
            <div className="report-section">
              <h2 className="section-title"><Swords size={18} /> Pattern Breaks</h2>
              <div className="report-cards">
                {r.pattern_breaks.map((item: any) => (
                  <div key={item.id} className="report-card break-card">
                    <div className="break-comparison">
                      <div className="break-conventional">
                        <span className="break-label">Conventional</span>
                        <p>{item.conventional_approach}</p>
                      </div>
                      <div className="break-arrow">→</div>
                      <div className="break-expert">
                        <span className="break-label">Expert's Way</span>
                        <p>{item.expert_approach}</p>
                      </div>
                    </div>
                    <p className="card-reasoning"><strong>Why:</strong> {item.reasoning}</p>
                    <blockquote className="card-quote">"{item.expert_quote}"</blockquote>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* War Stories */}
          {r.war_stories?.length > 0 && (
            <div className="report-section">
              <h2 className="section-title"><BookOpen size={18} /> War Stories</h2>
              <div className="report-cards">
                {r.war_stories.map((item: any) => (
                  <div key={item.id} className="report-card story-card">
                    <h3 className="story-title">{item.title}</h3>
                    <p className="card-desc">{item.summary}</p>
                    <div className="story-lesson">
                      <Crosshair size={14} />
                      <div>
                        <strong>Encoded Lesson:</strong>
                        <p>{item.encoded_lesson}</p>
                      </div>
                    </div>
                    <p className="card-untextbookable"><em>Why untextbookable:</em> {item.why_untextbookable}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actionable Playbooks */}
          {r.actionable_playbooks?.length > 0 && (
            <div className="report-section">
              <h2 className="section-title"><Route size={18} /> Actionable Playbooks</h2>
              <div className="report-cards">
                {r.actionable_playbooks.map((item: any) => (
                  <div key={item.id} className="report-card playbook-card">
                    <h3 className="playbook-title">{item.playbook_title}</h3>
                    <p className="card-context"><strong>When to use:</strong> {item.context}</p>
                    <ol className="playbook-steps">
                      {item.steps?.map((step: string, i: number) => (
                        <li key={i}>{step}</li>
                      ))}
                    </ol>
                    {item.caveats && <p className="card-caveats"><AlertCircle size={12} /> <strong>Caveats:</strong> {item.caveats}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Knowledge Gaps */}
          {r.knowledge_gaps?.length > 0 && (
            <div className="report-section">
              <h2 className="section-title"><HelpCircle size={18} /> Knowledge Gaps</h2>
              <div className="report-cards">
                {r.knowledge_gaps.map((item: any) => (
                  <div key={item.id} className="report-card gap-card">
                    <h3 className="gap-topic">{item.topic}</h3>
                    <p className="card-desc">{item.observation}</p>
                    <p className="card-followup"><strong>Suggested follow-up:</strong> {item.suggested_followup}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
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
            <span style={{ fontSize: '10px', color: '#64748b', fontFamily: 'monospace' }}>{sessionId.slice(0, 8)}</span>
          </div>
        </div>
        <div className="chat-header-right">
          <button className="btn-stop" onClick={handleEndInterview} disabled={isSynthesizing} title="End interview and extract knowledge">
            {isSynthesizing ? <Loader2 size={14} className="spin" /> : <StopCircle size={14} />}
            <span>Stop Interview</span>
          </button>
          <button className="btn-synth" onClick={handleSynthesizeKnowledge} disabled={isSynthesizing} title="Generate Tacit Knowledge Report">
            {isSynthesizing ? <Loader2 size={14} className="spin" /> : <Zap size={14} />}
            <span>{isSynthesizing ? 'Synthesizing...' : 'Extract Knowledge'}</span>
          </button>
          <button className="btn-ghost" onClick={downloadTranscript} style={{ marginRight: '8px' }}>
            <CloudDownload size={14} style={{ marginRight: '4px', verticalAlign: '-2px' }} /> Download
          </button>
          <button className="btn-ghost" onClick={() => setView('script_preview')} style={{ marginRight: '12px' }}>
            <FileText size={14} style={{ marginRight: '4px', verticalAlign: '-2px' }} /> View Script
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
