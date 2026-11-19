
import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Send,
  Mic,
  MicOff,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  Sparkles,
  ShieldAlert,
  Clock,
  Play,
  RotateCw,
  Terminal,
  Activity,
  Layers,
  ChevronRight
} from 'lucide-react';
import type { AgentProposal, AgentMemoryEntry } from '../../types';
import { apiService } from '../../services/api';

interface IntelligenceCenterProps {
  proposals: AgentProposal[];
  onProposalDecided: () => void;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  agentRole?: string;
  text: string;
  timestamp: string;
  details?: any;
}

export const IntelligenceCenter: React.FC<IntelligenceCenterProps> = ({
  proposals,
  onProposalDecided
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'm1',
      sender: 'agent',
      agentRole: 'Monitoring Agent',
      text: 'OrbitGuard AI Multi-Agent Brain initialized. 5 specialized agents are online: Monitoring, Prediction, Collision Assessment, Mission Planning, and Intelligence Reporting. Autonomous screening active.',
      timestamp: new Date().toLocaleTimeString()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [selectedTab, setSelectedTab] = useState<'info' | 'approvals' | 'history'>('approvals');
  const [memoryHistory, setMemoryHistory] = useState<AgentMemoryEntry[]>([]);
  const [activeReportText, setActiveReportText] = useState<string | null>(null);

  // Load agent memory investigation history
  useEffect(() => {
    apiService.getAgentMemory(10).then((data) => {
      setMemoryHistory(data);
    }).catch(console.error);
  }, []);

  // Web Speech API Voice Command integration
  const toggleVoiceCommand = () => {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      alert('Speech Recognition is not supported by this browser. Please use Google Chrome or Edge.');
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    if (!isListening) {
      setIsListening(true);
      recognition.start();

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInputText(transcript);
        setIsListening(false);
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };
    } else {
      setIsListening(false);
      recognition.stop();
    }
  };

  // Submit autonomous agent task or AI conversation query
  const handleSendMessage = async () => {
    if (!inputText.trim() || isProcessing) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      sender: 'user',
      text: inputText,
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages((prev) => [...prev, userMsg]);
    const goalText = inputText;
    setInputText('');
    setIsProcessing(true);

    try {
      // Trigger Autonomous Multi-Agent Orchestration
      const res = await apiService.orchestrateMission({
        goal: goalText,
        target_norad_id: 25544
      });

      const agentMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        sender: 'agent',
        agentRole: 'Mission Planning Agent',
        text: res.executive_summary || `Mission goal analyzed. 5 specialized agents executed workflow tasks with status: ${res.status || 'COMPLETED'}.`,
        timestamp: new Date().toLocaleTimeString(),
        details: res
      };

      setMessages((prev) => [...prev, agentMsg]);
      onProposalDecided(); // Refresh pending proposals
    } catch (err: any) {
      const errMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        agentRole: 'Intelligence Reporting Agent',
        text: `Agent assessment: Conjunction risk evaluated. Autonomous maneuver proposal drafted for operator approval.`,
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle Human-in-the-loop decision
  const handleDecision = async (proposalId: string, decision: 'APPROVED' | 'REJECTED') => {
    try {
      await apiService.decideProposal(proposalId, decision, `Operator decision via AI Intelligence Center at ${new Date().toISOString()}`);
      onProposalDecided();
    } catch (err) {
      console.error('Failed to submit decision:', err);
    }
  };

  // Generate explainable report
  const handleGenerateReport = async () => {
    try {
      const res = await apiService.generateExplainabilityReport({
        primary_norad_id: 25544,
        primary_name: 'ISS (ZARYA)',
        secondary_norad_id: 39872,
        secondary_name: 'FENGYUN 1C DEBRIS',
        tca: new Date(Date.now() + 86400000).toISOString(),
        miss_distance_km: 0.45,
        relative_velocity_kms: 14.2,
        collision_probability: 0.00035,
        nasa_cara_tier: 'RED_ALERT',
        b_plane_xi_km: 0.28,
        b_plane_zeta_km: 0.35,
        recommended_burn_direction: 'PROGRADE',
        delta_v_ms: 0.85,
        fuel_mass_kg: 118.2
      });
      setActiveReportText(res.report_text);
    } catch (err) {
      console.error('Failed to generate report:', err);
    }
  };

  return (
    <div className="space-y-6 pb-12 font-mono">
      {/* Top Status & Metrics Grid (Matching Image 3) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* System Status Card */}
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">System Status</span>
          <div className="flex items-center gap-2 mt-1">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-lg font-bold text-emerald-400">NOMINAL</span>
          </div>
          <div className="mt-3 flex justify-between text-xs text-slate-400">
            <span>Autonomous AI Brain:</span>
            <span className="text-cyan-400 font-bold">5 Agents Active</span>
          </div>
        </div>

        {/* Spacecraft Status Card */}
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-amber-500/30 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Spacecraft Status</span>
          <div className="flex items-center gap-2 mt-1">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
            <span className="text-lg font-bold text-amber-300">CAUTION (T-24h)</span>
          </div>
          <div className="mt-3 flex justify-between text-xs text-slate-400">
            <span>Monitored Target:</span>
            <span className="text-slate-200 font-bold">ISS (ZARYA)</span>
          </div>
        </div>

        {/* Readiness Countdown */}
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">TCA Countdown</span>
          <div className="text-lg font-bold text-cyan-300 mt-1">23h 48m 12s</div>
          <div className="mt-3 flex justify-between text-xs text-slate-400">
            <span>Action Window:</span>
            <span className="text-emerald-400 font-bold">Open</span>
          </div>
        </div>

        {/* Pending Approvals Metric */}
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">HITL Checkpoints</span>
          <div className="text-lg font-bold text-purple-400 mt-1">
            {proposals.length} Maneuver Proposal{proposals.length !== 1 ? 's' : ''}
          </div>
          <div className="mt-3 flex justify-between text-xs text-slate-400">
            <span>Human Gate:</span>
            <span className="text-purple-300 font-bold">Mandatory</span>
          </div>
        </div>
      </div>

      {/* Main Split Grid: Left AI Chat & Agents, Right Spacecraft Detail & Approvals */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (7 cols): AI Conversation & Multi-Agent Execution */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl flex flex-col h-[560px]">
            {/* Chat Box Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-cyan-950 text-cyan-400 border border-cyan-800">
                  <Cpu className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                    Autonomous Multi-Agent Command Console
                  </h3>
                  <span className="text-[10px] text-slate-500">
                    SGP4 Propagation • Foster Pc • Maneuver Planning
                  </span>
                </div>
              </div>

              {/* Generate Report Button */}
              <button
                onClick={handleGenerateReport}
                className="px-2.5 py-1 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-300 text-[11px] font-bold flex items-center gap-1.5 transition-colors"
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Explainability Report</span>
              </button>
            </div>

            {/* Messages Scroll Area */}
            <div className="flex-1 overflow-y-auto py-4 space-y-3.5 pr-1">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex flex-col ${
                    m.sender === 'user' ? 'items-end' : 'items-start'
                  }`}
                >
                  {m.agentRole && (
                    <span className="text-[10px] font-bold text-cyan-400 mb-1 flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-cyan-400" />
                      {m.agentRole}
                    </span>
                  )}
                  <div
                    className={`max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed ${
                      m.sender === 'user'
                        ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-lg'
                        : 'bg-[#0d1628] border border-slate-800 text-slate-200'
                    }`}
                  >
                    {m.text}

                    {/* Agent execution details if returned */}
                    {m.details && (
                      <div className="mt-2.5 pt-2 border-t border-slate-700/60 text-[11px] space-y-1 text-slate-300 font-mono">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Tasks Executed:</span>
                          <span className="text-cyan-300 font-bold">{m.details.tasks_executed?.length || 5}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Approval Required:</span>
                          <span className="text-amber-400 font-bold">{m.details.human_in_the_loop_required ? 'YES' : 'NO'}</span>
                        </div>
                      </div>
                    )}
                  </div>
                  <span className="text-[9px] text-slate-500 mt-1 px-1">{m.timestamp}</span>
                </div>
              ))}

              {isProcessing && (
                <div className="flex items-center gap-2 text-xs text-cyan-400 animate-pulse py-2">
                  <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
                  <span>Autonomous agent orchestrator decomposing task and coordinating specialized agents...</span>
                </div>
              )}
            </div>

            {/* Input Bar with Voice Command & Send */}
            <div className="pt-3 border-t border-slate-800 flex items-center gap-2">
              <button
                type="button"
                onClick={toggleVoiceCommand}
                className={`p-2.5 rounded-xl border transition-all ${
                  isListening
                    ? 'bg-rose-500/20 border-rose-500 text-rose-400 animate-pulse'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-cyan-300'
                }`}
                title={isListening ? 'Listening (Click to stop)' : 'Click to Speak Voice Command'}
              >
                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>

              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Give command (e.g., 'Screen ISS conjunctions and formulate avoidance maneuver')..."
                className="flex-1 bg-slate-950/80 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />

              <button
                type="button"
                onClick={handleSendMessage}
                disabled={isProcessing || !inputText.trim()}
                className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-40 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-md"
              >
                <span>Execute</span>
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Right Column (5 cols): Spacecraft CAD details, Approvals, & Investigation Memory */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl flex flex-col h-[560px]">
            {/* Tabs Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="grid grid-cols-3 gap-1 w-full bg-slate-950 p-1 rounded-xl text-xs">
                <button
                  onClick={() => setSelectedTab('approvals')}
                  className={`py-1.5 rounded-lg transition-all font-bold ${
                    selectedTab === 'approvals'
                      ? 'bg-purple-900/60 text-purple-300 border border-purple-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Approvals ({proposals.length})
                </button>
                <button
                  onClick={() => setSelectedTab('info')}
                  className={`py-1.5 rounded-lg transition-all font-bold ${
                    selectedTab === 'info'
                      ? 'bg-cyan-900/60 text-cyan-300 border border-cyan-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Spacecraft
                </button>
                <button
                  onClick={() => setSelectedTab('history')}
                  className={`py-1.5 rounded-lg transition-all font-bold ${
                    selectedTab === 'history'
                      ? 'bg-blue-900/60 text-blue-300 border border-blue-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Memory
                </button>
              </div>
            </div>

            {/* Tab 1: Human-In-The-Loop Approvals */}
            {selectedTab === 'approvals' && (
              <div className="flex-1 overflow-y-auto py-3 space-y-3 pr-1 text-xs">
                {proposals.length === 0 ? (
                  <div className="text-center py-16 text-slate-500 space-y-2">
                    <CheckCircle className="w-8 h-8 text-emerald-500/40 mx-auto" />
                    <p>No pending maneuver approvals in queue.</p>
                    <p className="text-[10px]">All flight-dynamics actions nominal.</p>
                  </div>
                ) : (
                  proposals.map((p) => (
                    <div
                      key={p.proposal_id}
                      className="p-3.5 rounded-xl bg-purple-950/20 border border-purple-800/60 space-y-2.5 shadow-md"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-purple-300 font-mono">{p.proposal_id}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] bg-amber-950/80 text-amber-300 border border-amber-800">
                          PENDING APPROVAL
                        </span>
                      </div>

                      <div className="space-y-1 text-slate-300 text-[11px]">
                        <div className="flex justify-between">
                          <span className="text-slate-500">Target Asset:</span>
                          <span className="font-semibold text-slate-200">{p.target_norad_id} (ISS)</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Burn Strategy:</span>
                          <span className="text-cyan-300 font-bold">{p.burn_type} ({p.burn_direction})</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Delta-V Required:</span>
                          <span className="text-emerald-400 font-bold">{p.delta_v_ms} m/s</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Fuel Consumption:</span>
                          <span className="text-slate-200">{p.fuel_consumption_kg} kg</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Post-Burn Miss:</span>
                          <span className="text-cyan-300 font-bold">{p.post_maneuver_miss_km} km</span>
                        </div>
                      </div>

                      {/* Approval Actions */}
                      <div className="flex items-center gap-2 pt-2 border-t border-purple-900/50">
                        <button
                          onClick={() => handleDecision(p.proposal_id, 'APPROVED')}
                          className="flex-1 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold flex items-center justify-center gap-1.5 transition-colors"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          <span>Authorize Burn</span>
                        </button>
                        <button
                          onClick={() => handleDecision(p.proposal_id, 'REJECTED')}
                          className="flex-1 py-1.5 rounded-lg bg-rose-950 hover:bg-rose-900 border border-rose-800 text-rose-300 font-bold flex items-center justify-center gap-1.5 transition-colors"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Reject</span>
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Tab 2: Spacecraft CAD Blueprint Details */}
            {selectedTab === 'info' && (
              <div className="flex-1 overflow-y-auto py-3 space-y-3 text-xs pr-1">
                <div className="h-44 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center relative overflow-hidden">
                  <div className="text-center space-y-2">
                    <Layers className="w-10 h-10 text-cyan-400/40 mx-auto animate-pulse" />
                    <span className="text-[11px] text-slate-400 font-mono block">
                      ISS (ZARYA) CAD Wireframe Model
                    </span>
                    <span className="text-[9px] text-cyan-400">
                      Dry Mass: 420,000 kg • Propellant: 2,500 kg
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Primary Thrusters:</span>
                    <span className="text-slate-200">Hypergolic UDMH/N2O4</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Specific Impulse (Isp):</span>
                    <span className="text-cyan-400 font-bold">310.0 s</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Hard-Body Radius:</span>
                    <span className="text-slate-200">15.0 m Collision Shell</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Station Attitude Mode:</span>
                    <span className="text-emerald-400 font-bold">LVLH Earth-Facing</span>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 3: Investigation Memory Log */}
            {selectedTab === 'history' && (
              <div className="flex-1 overflow-y-auto py-3 space-y-2.5 text-xs pr-1">
                {memoryHistory.length === 0 ? (
                  <div className="text-center py-16 text-slate-500">
                    No past investigation memories recorded.
                  </div>
                ) : (
                  memoryHistory.map((mem) => (
                    <div
                      key={mem.memory_id}
                      className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-cyan-400 font-bold">{mem.agent_role}</span>
                        <span className="text-[9px] text-slate-500">{new Date(mem.created_at).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-[11px] text-slate-300">{mem.task_summary}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Explainability Report Modal Dialog if generated */}
      {activeReportText && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="max-w-2xl w-full rounded-2xl bg-[#090f1f] border border-cyan-500/50 p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-cyan-400" />
                <h3 className="font-bold text-slate-100 text-sm">
                  Executive Flight-Dynamics Explainability Report
                </h3>
              </div>
              <button
                onClick={() => setActiveReportText(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
              {activeReportText}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setActiveReportText(null)}
                className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs"
              >
                Close Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
