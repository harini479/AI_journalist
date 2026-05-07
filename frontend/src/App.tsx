import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { 
  Mic, 
  MicOff, 
  Send, 
  BrainCircuit, 
  ChevronRight, 
  History,
  ShieldCheck,
  CloudDownload,
  Link,
  Loader2,
  CheckCircle,
  Terminal,
  Activity,
  FileText,
  Map,
  Compass
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
  const [view, setView] = useState<'landing' | 'prepare' | 'interview' | 'ingest'>('landing');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isPreparing, setIsPreparing] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [ingestionStatus, setIngestionStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [ingestionResult, setIngestionResult] = useState<string>('');
  const [script, setScript] = useState<InterviewScript | null>(null);
  const [themes, setThemes] = useState<any[]>([]);
  const [openDecisionId, setOpenDecisionId] = useState<string | null>(null);
  const [scriptProgress, setScriptProgress] = useState<string>('0/0');
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionId = 'demo-session-002'; // Unique for this demo

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, openDecisionId]);

  // Trigger First Hook automatically when entering interview view
  useEffect(() => {
    if (view === 'interview' && messages.length === 0) {
      handleSend('');
    }
  }, [view]);

  const handlePrepareInterview = async () => {
    setIsPreparing(true);
    setView('prepare');
    try {
      const response = await axios.post(`${API_BASE}/prepare-interview`, {
        user_session_id: sessionId,
        topic: "Technical Scaling in SaaS"
      });
      setScript(response.data.script);
      setThemes(response.data.themes);
    } catch (error) {
      console.error("Preparation error:", error);
    } finally {
      setIsPreparing(false);
    }
  };

  const handleSend = async (text: string) => {
    if (!text.trim() && messages.length > 0) return;

    if (text.trim()) {
      const expertMsg: Message = {
        id: Date.now().toString(),
        role: 'expert',
        text: text,
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, expertMsg]);
    }
    
    setInputText('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/generate-question`, {
        expert_answer: text,
        user_session_id: sessionId
      });

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        text: response.data.question,
        timestamp: Date.now(),
        decision: response.data.decision,
        script_progress: response.data.script_progress
      };

      setMessages(prev => [...prev, aiMsg]);
      setScriptProgress(response.data.script_progress || 'Reactive');
    } catch (error) {
      console.error("Error calling backend:", error);
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        text: "I encountered a synchronization error with the Knowledge Hub. Please try again.",
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleRecording = () => {
    setIsRecording(!isRecording);
    if (!isRecording) {
      console.log("Starting Web Audio API capture...");
    } else {
      console.log("Stopping capture and processing audio...");
      handleSend("In my experience, horizontal scaling is preferred for stateless microservices, but database sharding is where the real complexity begins.");
    }
  };

  const handleIngestYoutube = async () => {
    if (!youtubeUrl.trim()) return;
    setIngestionStatus('loading');
    try {
      const response = await axios.post(`${API_BASE}/ingest-youtube`, {
        url: youtubeUrl
      });
      setIngestionStatus('success');
      setIngestionResult(response.data.message);
    } catch (error) {
      console.error("Ingestion error:", error);
      setIngestionStatus('error');
    }
  };

  if (view === 'landing') {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-slate-50 p-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full landing-bg-glow pointer-events-none" />
        
        <div className="max-w-3xl w-full text-center relative z-10">
          <div className="flex justify-center mb-8">
            <div className="p-4 rounded-3xl bg-indigo-500/10 border border-indigo-500/20 shadow-2xl shadow-indigo-500/10 animate-float">
              <BrainCircuit className="w-16 h-16 text-indigo-400" />
            </div>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-black tracking-tight mb-6 hero-title">
            Cognitive Extraction Engine
          </h1>
          <p className="text-xl text-slate-400 mb-12 max-w-2xl mx-auto font-medium leading-relaxed">
            Synthesizing expert tacit knowledge and YouTube transcripts into structured, grounded intelligence.
          </p>

          <div className="flex flex-wrap justify-center gap-6">
            <button
              onClick={handlePrepareInterview}
              className="px-8 py-5 rounded-2xl premium-gradient text-white font-bold text-lg shadow-2xl shadow-indigo-500/30 hover:scale-105 transition-all flex items-center gap-3"
            >
              Initialize Interview <ChevronRight className="w-5 h-5" />
            </button>
            <button
              onClick={() => setView('ingest')}
              className="px-8 py-5 rounded-2xl bg-slate-900 border border-slate-800 text-slate-300 font-bold text-lg hover:bg-slate-800 hover:scale-105 transition-all flex items-center gap-3"
            >
              <CloudDownload className="w-5 h-5 text-accent" /> Ingestion Tower
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (view === 'prepare') {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-slate-50 p-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(circle_at_50%_10%,_rgba(99,102,241,0.1),_transparent_60%)] pointer-events-none" />
        
        <div className="max-w-4xl w-full relative z-10">
          <button 
            onClick={() => setView('landing')}
            className="mb-8 text-slate-500 hover:text-white transition-all flex items-center gap-2 text-xs font-black uppercase tracking-widest group"
          >
            <ChevronRight className="w-4 h-4 rotate-180 group-hover:-translate-x-1 transition-transform" /> Back to Dashboard
          </button>

          <div className="glass-morphism p-10 rounded-[2.5rem] border border-slate-800 shadow-2xl">
            {isPreparing ? (
              <div className="py-20 flex flex-col items-center text-center">
                <Loader2 className="w-16 h-16 text-indigo-400 animate-spin mb-8" />
                <h2 className="text-3xl font-black mb-4">Researching Knowledge Base</h2>
                <p className="text-slate-400 font-medium max-w-md">Scanning hierarchical chunks, extracting core themes, and crafting a targeted interview script...</p>
              </div>
            ) : (
              <div className="space-y-10 animate-in fade-in duration-700">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-5">
                    <div className="p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/20">
                      <FileText className="w-8 h-8 text-indigo-400" />
                    </div>
                    <div>
                      <h2 className="text-3xl font-black tracking-tight">Interview Script</h2>
                      <p className="text-slate-500 font-medium">12 Questions across 4 Narrative Phases</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setView('interview')}
                    className="px-8 py-4 rounded-2xl premium-gradient text-white font-black text-lg shadow-xl hover:scale-105 transition-all"
                  >
                    Start Interview
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="space-y-6">
                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 flex items-center gap-2">
                      <Map className="w-4 h-4" /> Extracted Themes
                    </h3>
                    <div className="space-y-4">
                      {themes.map((theme: any) => (
                        <div key={theme.theme_id} className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-indigo-500/30 transition-all">
                          <h4 className="font-bold text-indigo-400 mb-2">{theme.theme_title}</h4>
                          <p className="text-sm text-slate-400 leading-relaxed">{theme.editorial_rationale}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-6">
                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 flex items-center gap-2">
                      <Terminal className="w-4 h-4" /> Script Preview
                    </h3>
                    <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                      {Object.entries(script?.interview_arc || {}).map(([key, phase]: [string, any]) => (
                        <div key={key} className="space-y-3">
                          <div className="text-[10px] font-black uppercase tracking-widest text-indigo-500/50 mb-2">
                            {key.replace('phase_', '').replace('_', ' ')}
                          </div>
                          {phase.questions.map((q: any) => (
                            <div key={q.question_id} className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-sm font-medium">
                              {q.question_text}
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (view === 'ingest') {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-slate-50 p-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(circle_at_50%_10%,_rgba(99,102,241,0.1),_transparent_60%)] pointer-events-none" />
        
        <div className="max-w-2xl w-full relative z-10">
          <button 
            onClick={() => setView('landing')}
            className="mb-8 text-slate-500 hover:text-white transition-all flex items-center gap-2 text-xs font-black uppercase tracking-widest group"
          >
            <ChevronRight className="w-4 h-4 rotate-180 group-hover:-translate-x-1 transition-transform" /> Back to Dashboard
          </button>

          <div className="glass-morphism p-10 rounded-[2.5rem] border border-slate-800 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-10">
              <CloudDownload className="w-24 h-24 text-accent" />
            </div>
            
            <div className="flex items-center gap-5 mb-10">
              <div className="p-4 rounded-2xl bg-accent/10 border border-accent/20">
                <CloudDownload className="w-8 h-8 text-accent" />
              </div>
              <div>
                <h2 className="text-3xl font-black tracking-tight">Ingestion Tower</h2>
                <p className="text-slate-500 font-medium">Knowledge Hub Synchronization Engine</p>
              </div>
            </div>

            <div className="space-y-8">
              <div className="space-y-3">
                <label className="text-xs font-black uppercase tracking-widest text-slate-500 ml-1">YouTube Source URL</label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none">
                    <Link className="w-5 h-5 text-slate-600 group-focus-within:text-accent transition-colors" />
                  </div>
                  <input 
                    type="text"
                    className="w-full bg-slate-900 border border-slate-800 rounded-2xl py-5 pl-14 pr-5 text-white focus:border-accent outline-none transition-all placeholder:text-slate-700 font-medium text-lg"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={youtubeUrl}
                    onChange={(e) => setYoutubeUrl(e.target.value)}
                  />
                </div>
              </div>

              <button 
                onClick={handleIngestYoutube}
                disabled={ingestionStatus === 'loading'}
                className="w-full py-5 rounded-2xl premium-gradient text-white font-black text-xl shadow-2xl shadow-accent/20 hover:scale-[1.02] active:scale-95 transition-all disabled:opacity-50 disabled:scale-100 flex items-center justify-center gap-4"
              >
                {ingestionStatus === 'loading' ? (
                  <><Loader2 className="w-6 h-6 animate-spin" /> Running Hybrid Pipeline...</>
                ) : (
                  'Synchronize Knowledge'
                )}
              </button>

              {ingestionStatus === 'success' && (
                <div className="p-6 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex gap-5 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div className="p-2 bg-emerald-500/20 rounded-lg h-fit">
                    <CheckCircle className="w-6 h-6 text-emerald-400" />
                  </div>
                  <div>
                    <h4 className="font-bold text-emerald-400 text-lg">Sync Successful</h4>
                    <p className="text-sm text-emerald-500/70 mt-1 leading-relaxed">{ingestionResult}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-container">
      <header className="p-6 flex items-center justify-between border-b glass-morphism sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setView('landing')}
            className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 transition-all"
          >
            <BrainCircuit className="w-6 h-6" />
          </button>
          <div>
            <h1 className="text-xl font-black tracking-tight">AI Journalist</h1>
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-emerald-500 font-black">
              <ShieldCheck className="w-3 h-3" /> Zero-Trust Grounding
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-5">
          <div className="flex flex-col items-end">
            <div className="px-3 py-1 rounded-lg bg-slate-900 border border-slate-800 text-[10px] font-black uppercase tracking-widest text-slate-400">
              Script Progress
            </div>
            <div className="text-xs font-black text-indigo-400 mt-1">{scriptProgress} Questions</div>
          </div>
          <button className="p-2 text-slate-500 hover:text-white transition-colors">
            <History className="w-5 h-5" />
          </button>
        </div>
      </header>

      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-8 flex flex-col space-y-6"
      >
        {messages.map((msg) => (
          <div key={msg.id} className="flex flex-col group">
            <div 
              className={`message-bubble max-w-[80%] ${msg.role === 'expert' ? 'expert-message self-end' : 'ai-message self-start'}`}
            >
              {msg.role === 'ai' && (
                <div className="flex items-center justify-between gap-2 mb-3 text-[10px] font-black uppercase tracking-widest text-accent-light opacity-80">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-3 h-3" /> Grounded Follow-up
                  </div>
                  {msg.script_progress && (
                    <span className="text-slate-500">Q {msg.script_progress}</span>
                  )}
                </div>
              )}
              <p className="font-medium leading-relaxed">{msg.text}</p>
            </div>
            
            {msg.role === 'ai' && msg.decision && (
              <div className="self-start ml-4 mt-2">
                <button 
                  onClick={() => setOpenDecisionId(openDecisionId === msg.id ? null : msg.id)}
                  className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-slate-500 hover:text-indigo-400 transition-colors"
                >
                  <Activity className="w-3 h-3" /> 
                  {openDecisionId === msg.id ? 'Hide Decision Log' : 'View Decision Log'}
                </button>
                
                {openDecisionId === msg.id && (
                  <div className="mt-3 p-5 rounded-2xl bg-slate-900 border border-slate-800 w-full max-w-xl animate-in slide-in-from-top-2 duration-300">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                        <span className="text-[10px] font-black uppercase tracking-widest text-indigo-500">Action: {msg.decision.action}</span>
                        <span className={`text-[10px] font-black uppercase tracking-widest ${msg.decision.scripted_question_resolved ? 'text-emerald-500' : 'text-amber-500'}`}>
                          {msg.decision.scripted_question_resolved ? '✓ Question Resolved' : '○ Continuing Thread'}
                        </span>
                      </div>
                      
                      <div className="space-y-1">
                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-600">Internal Monologue</span>
                        <p className="text-xs text-slate-300 italic">"{msg.decision.internal_monologue}"</p>
                      </div>

                      {msg.decision.tangent_detected?.exists && (
                        <div className="p-3 rounded-lg bg-indigo-500/5 border border-indigo-500/10">
                          <span className="text-[10px] font-black uppercase tracking-widest text-indigo-400 flex items-center gap-2">
                            <Compass className="w-3 h-3" /> Tangent Detected
                          </span>
                          <p className="text-[11px] text-indigo-300/70 mt-1">Found high-value thread: "{msg.decision.tangent_detected.topic}"</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="ai-message message-bubble self-start opacity-60 flex items-center gap-4">
            <div className="flex gap-1.5">
              <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: '200ms' }} />
              <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: '400ms' }} />
            </div>
            <span className="text-xs font-black uppercase tracking-widest text-slate-400">Synthesizing Context...</span>
          </div>
        )}
      </div>

      <footer className="stt-bar">
        <div className="max-w-2xl mx-auto flex items-center gap-4 bg-slate-900/80 backdrop-blur-md p-3 rounded-3xl border border-slate-800 focus-within:border-accent focus-within:shadow-[0_0_30px_rgba(99,102,241,0.15)] transition-all">
          <button 
            onClick={toggleRecording}
            className={`record-btn ${isRecording ? 'active' : ''}`}
          >
            {isRecording ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
          </button>
          
          <input 
            type="text" 
            className="flex-1 bg-transparent border-none outline-none py-4 px-4 text-slate-50 placeholder:text-slate-600 font-medium text-lg"
            placeholder="Document your insight..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend(inputText)}
          />

          <button 
            onClick={() => handleSend(inputText)}
            className="p-4 bg-accent/10 rounded-2xl text-accent hover:text-accent-light hover:bg-accent/20 transition-all hover:scale-105 active:scale-90 flex items-center justify-center"
          >
            <Send className="w-6 h-6" />
          </button>
        </div>
      </footer>
    </div>
  );
};

export default App;
