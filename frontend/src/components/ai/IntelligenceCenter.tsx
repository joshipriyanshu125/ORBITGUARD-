import React, { useEffect, useMemo, useState } from 'react';
import {
  Cpu,
  Send,
  Mic,
  MicOff,
  CheckCircle,
  XCircle,
  Sparkles,
  FileText,
  User
} from 'lucide-react';
import type { AgentProposal, AgentMemoryEntry, ConjunctionSummary, SatelliteSummary } from '../../types';
import { apiService } from '../../services/api';
import { RiskInterpretationNotice } from '../risk/RiskInterpretationNotice';

interface IntelligenceCenterProps {
  proposals: AgentProposal[];
  conjunctions: ConjunctionSummary[];
  selectedSatellite: SatelliteSummary | null;
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

const formatUtc = (value?: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.toISOString().replace('T', ' ').slice(0, 19)} UTC`;
};

export const IntelligenceCenter: React.FC<IntelligenceCenterProps> = ({
  proposals,
  conjunctions,
  selectedSatellite,
  onProposalDecided
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'm1',
      sender: 'agent',
      agentRole: 'Monitoring Agent',
      text: 'OrbitGuard multi-agent orchestrator ready. Monitoring, Prediction, Collision Assessment, Mission Planning, and Intelligence Reporting agents use the live catalog, SGP4 propagation, and stored conjunction records.',
      timestamp: new Date().toLocaleTimeString()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [selectedTab, setSelectedTab] = useState<'info' | 'approvals' | 'history'>('approvals');
  const [memoryHistory, setMemoryHistory] = useState<AgentMemoryEntry[]>([]);
  const [activeReportText, setActiveReportText] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [operatorName, setOperatorName] = useState('');
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [selectedConjunctionId, setSelectedConjunctionId] = useState('');

  useEffect(() => {
    apiService.getAgentMemory(10).then(setMemoryHistory).catch(() => setMemoryHistory([]));
  }, []);

  useEffect(() => {
    if (!selectedConjunctionId && conjunctions.length > 0) {
      setSelectedConjunctionId(conjunctions[0].conjunction_id);
    }
  }, [conjunctions, selectedConjunctionId]);

  const selectedConjunction = useMemo(
    () => conjunctions.find((c) => c.conjunction_id === selectedConjunctionId) ?? null,
    [conjunctions, selectedConjunctionId]
  );

  const highRiskCount = conjunctions.filter(
    (c) => c.risk_tier === 'CRITICAL' || c.risk_tier === 'HIGH'
  ).length;

  // Web Speech API voice command integration
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
        setInputText(event.results[0][0].transcript);
        setIsListening(false);
      };

      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);
    } else {
      setIsListening(false);
      recognition.stop();
    }
  };

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
      const res = await apiService.orchestrateMission({
        goal: goalText,
        ...(selectedSatellite ? { target_norad_id: selectedSatellite.norad_id } : {})
      });

      const reply: ChatMessage = {
        id: `a-${Date.now()}`,
        sender: 'agent',
        agentRole: 'Intelligence Reporting Agent',
        text: res.findings_summary || 'The orchestrator returned no findings summary.',
        timestamp: new Date().toLocaleTimeString(),
        details: res
      };

      setMessages((prev) => [...prev, reply]);
      onProposalDecided();
      apiService.getAgentMemory(10).then(setMemoryHistory).catch(() => undefined);
    } catch (err: any) {
      const reply: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        agentRole: 'Orchestrator Error',
        text: err?.response?.data?.detail || 'The agent workflow could not be executed.',
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages((prev) => [...prev, reply]);
    } finally {
      setIsProcessing(false);
    }
  };

  // Human-in-the-loop decision requires an explicit operator identity.
  const handleDecision = async (proposalId: string, decision: 'APPROVED' | 'REJECTED') => {
    setDecisionError(null);
    if (!operatorName.trim()) {
      setDecisionError('Enter the operator name before authorizing or rejecting a burn.');
      return;
    }
    try {
      await apiService.decideProposal(
        proposalId,
        decision,
        operatorName.trim(),
        `Operator decision via AI Intelligence Center at ${new Date().toISOString()}`
      );
      onProposalDecided();
    } catch (err: any) {
      setDecisionError(err?.response?.data?.detail || 'Failed to submit the proposal decision.');
    }
  };

  // Report is generated from real catalog TLEs for the selected stored conjunction.
  const handleGenerateReport = async () => {
    setReportError(null);
    if (!selectedConjunction) {
      setReportError('No stored conjunction is selected. Run conjunction screening first.');
      return;
    }
    setIsGeneratingReport(true);
    try {
      const res = await apiService.generateExplainabilityReport({
        primary_norad_id: selectedConjunction.primary_norad_id,
        secondary_norad_id: selectedConjunction.secondary_norad_id,
        event_id: selectedConjunction.conjunction_id,
        tca: selectedConjunction.tca,
        primary_name: selectedConjunction.primary_name,
        secondary_name: selectedConjunction.secondary_name,
        secondary_type: selectedConjunction.secondary_type
      });
      setActiveReportText(res.report_text);
    } catch (err: any) {
      setReportError(err?.response?.data?.detail || 'Failed to generate the explainability report.');
    } finally {
      setIsGeneratingReport(false);
    }
  };

  return (
    <div className="space-y-6 pb-12 font-mono">
      {/* Real-data status metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Pending Proposals</span>
          <div className={`text-lg font-bold mt-1 ${proposals.length > 0 ? 'text-amber-300' : 'text-slate-300'}`}>
            {proposals.length}
          </div>
          <div className="mt-3 flex justify-between text-xs text-slate-400">
            <span>Human Gate:</span>
            <span className="text-amber-300 font-bold">Mandatory</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Stored Conjunctions</span>
          <div className="text-lg font-bold text-cyan-300 mt-1">{conjunctions.length}</div>
          <div className="mt-3 flex justify-between text-xs text-slate-400">
            <span>High / Critical:</span>
            <span className="text-rose-400 font-bold">{highRiskCount}</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Active Target</span>
          <div className="text-sm font-bold text-slate-200 mt-2 truncate">
            {selectedSatellite ? selectedSatellite.name : 'No catalog object selected'}
          </div>
          <div className="mt-2 text-[10px] text-slate-500">
            {selectedSatellite ? `NORAD ${selectedSatellite.norad_id}` : 'Select a target in Mission Control'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Selected Conjunction TCA</span>
          <div className="text-xs font-bold text-slate-200 mt-2">
            {selectedConjunction ? formatUtc(selectedConjunction.tca) : 'None'}
          </div>
          <div className="mt-2 text-[10px] text-slate-500 truncate">
            {selectedConjunction ? selectedConjunction.conjunction_id : 'Run screening to populate'}
          </div>
        </div>
      </div>

      <RiskInterpretationNotice compact />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Conversation */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl flex flex-col h-[560px]">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-cyan-950 text-cyan-400 border border-cyan-800">
                  <Cpu className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                    Autonomous Multi-Agent Command Console
                  </h3>
                  <span className="text-[10px] text-slate-500">
                    Real catalog state • SGP4 propagation • Stored conjunctions
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={selectedConjunctionId}
                  onChange={(e) => setSelectedConjunctionId(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-[11px] text-slate-300 max-w-52"
                >
                  <option value="">No conjunction selected</option>
                  {conjunctions.map((c) => (
                    <option key={c.conjunction_id} value={c.conjunction_id}>
                      {c.conjunction_id}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleGenerateReport}
                  disabled={isGeneratingReport}
                  className="px-2.5 py-1 rounded-lg bg-cyan-950 hover:bg-cyan-900 disabled:opacity-50 border border-cyan-700/60 text-cyan-300 text-[11px] font-bold flex items-center gap-1.5 transition-colors"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>{isGeneratingReport ? 'Generating…' : 'Report'}</span>
                </button>
              </div>
            </div>

            {reportError && <p className="text-[11px] text-rose-400 pt-2">{reportError}</p>}

            <div className="flex-1 overflow-y-auto py-4 space-y-3.5 pr-1">
              {messages.map((m) => (
                <div key={m.id} className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}>
                  {m.agentRole && (
                    <span className="text-[10px] font-bold text-cyan-400 mb-1 flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-cyan-400" />
                      {m.agentRole}
                    </span>
                  )}
                  <div
                    className={`max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed whitespace-pre-wrap ${
                      m.sender === 'user'
                        ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-lg'
                        : 'bg-[#0d1628] border border-slate-800 text-slate-200'
                    }`}
                  >
                    {m.text}

                    {m.details && (
                      <div className="mt-2.5 pt-2 border-t border-slate-700/60 text-[11px] space-y-1 text-slate-300 font-mono">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Agent Steps:</span>
                          <span className="text-cyan-300 font-bold">{m.details.trace?.length ?? 0}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Approval Required:</span>
                          <span className="text-amber-400 font-bold">{m.details.approval_required ? 'YES' : 'NO'}</span>
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
                  <span>Orchestrator is coordinating specialized agents against the catalog…</span>
                </div>
              )}
            </div>

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
                placeholder={
                  selectedSatellite
                    ? `Ask about ${selectedSatellite.name} or a stored conjunction…`
                    : 'Select a catalog target, then describe the investigation…'
                }
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

        {/* Right panel */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl flex flex-col h-[560px]">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="grid grid-cols-3 gap-1 w-full bg-slate-950 p-1 rounded-xl text-xs">
                <button
                  onClick={() => setSelectedTab('approvals')}
                  className={`py-1.5 rounded-lg transition-all font-bold ${
                    selectedTab === 'approvals'
                      ? 'bg-cyan-900/60 text-cyan-300 border border-cyan-500/40'
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
                  Conjunction
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

            {selectedTab === 'approvals' && (
              <div className="flex-1 overflow-y-auto py-3 space-y-3 pr-1 text-xs">
                <label className="flex items-center gap-2 rounded-xl bg-slate-950 border border-slate-800 px-3 py-2">
                  <User className="w-3.5 h-3.5 text-slate-500" />
                  <input
                    value={operatorName}
                    onChange={(e) => setOperatorName(e.target.value)}
                    placeholder="Operator name (required for decisions)"
                    className="w-full bg-transparent text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
                  />
                </label>
                {decisionError && <p className="text-[11px] text-rose-400">{decisionError}</p>}

                {proposals.length === 0 ? (
                  <div className="text-center py-14 text-slate-500 space-y-2">
                    <CheckCircle className="w-8 h-8 text-emerald-500/40 mx-auto" />
                    <p>No pending maneuver approvals.</p>
                    <p className="text-[10px]">Proposals appear after the orchestrator assesses a stored conjunction.</p>
                  </div>
                ) : (
                  proposals.map((p) => (
                    <div
                      key={p.proposal_id}
                      className="p-3.5 rounded-xl bg-cyan-950/20 border border-cyan-800/60 space-y-2.5 shadow-md"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-cyan-300 font-mono">{p.proposal_id}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] bg-amber-950/80 text-amber-300 border border-amber-800">
                          {p.approval_status}
                        </span>
                      </div>

                      <div className="space-y-1 text-slate-300 text-[11px]">
                        <div className="flex justify-between">
                          <span className="text-slate-500">Target Asset:</span>
                          <span className="font-semibold text-slate-200">
                            {p.target_name ? `${p.target_name} (${p.target_norad_id})` : `NORAD ${p.target_norad_id}`}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Conjunction:</span>
                          <span className="text-slate-200">{p.conjunction_id}</span>
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
                          <span className="text-slate-200">
                            {p.fuel_consumption_kg != null ? `${p.fuel_consumption_kg} kg` : 'Not computed'}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Post-Burn Miss:</span>
                          <span className="text-cyan-300 font-bold">{p.post_maneuver_miss_km} km</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Burn Epoch:</span>
                          <span className="text-slate-200">{formatUtc(p.burn_epoch)}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 pt-2 border-t border-cyan-900/50">
                        <button
                          onClick={() => handleDecision(p.proposal_id, 'APPROVED')}
                          disabled={!operatorName.trim()}
                          className="flex-1 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-bold flex items-center justify-center gap-1.5 transition-colors"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          <span>Authorize</span>
                        </button>
                        <button
                          onClick={() => handleDecision(p.proposal_id, 'REJECTED')}
                          disabled={!operatorName.trim()}
                          className="flex-1 py-1.5 rounded-lg bg-rose-950 hover:bg-rose-900 disabled:opacity-40 border border-rose-800 text-rose-300 font-bold flex items-center justify-center gap-1.5 transition-colors"
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

            {selectedTab === 'info' && (
              <div className="flex-1 overflow-y-auto py-3 space-y-3 text-xs pr-1">
                {!selectedConjunction ? (
                  <div className="text-center py-16 text-slate-500">
                    No stored conjunction is selected.
                  </div>
                ) : (
                  <>
                    <div className="space-y-1.5 text-[11px]">
                      {[
                        ['Event', selectedConjunction.conjunction_id],
                        ['Primary', `${selectedConjunction.primary_name} (${selectedConjunction.primary_norad_id})`],
                        ['Secondary', `${selectedConjunction.secondary_name} (${selectedConjunction.secondary_norad_id})`],
                        ['Secondary Type', selectedConjunction.secondary_type ?? 'UNKNOWN'],
                        ['TCA', formatUtc(selectedConjunction.tca)],
                        ['Miss Distance', `${selectedConjunction.miss_distance_km.toFixed(3)} km`],
                        ['Relative Velocity', `${selectedConjunction.relative_speed_kms.toFixed(2)} km/s`],
                        ['Estimated proximity tier', selectedConjunction.risk_tier ?? 'UNKNOWN'],
                        ['Status', selectedConjunction.status ?? '—']
                      ].map(([label, value]) => (
                        <div key={label} className="flex justify-between gap-3 border-b border-slate-800/50 py-1">
                          <span className="text-slate-500">{label}</span>
                          <span className="text-slate-200 text-right break-all">{value}</span>
                        </div>
                      ))}
                    </div>

                    <button
                      onClick={handleGenerateReport}
                      disabled={isGeneratingReport}
                      className="w-full py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-bold flex items-center justify-center gap-2"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      {isGeneratingReport ? 'Synthesizing…' : 'Generate explainability report'}
                    </button>
                  </>
                )}
                {reportError && <p className="text-[11px] text-rose-400">{reportError}</p>}
              </div>
            )}

            {selectedTab === 'history' && (
              <div className="flex-1 overflow-y-auto py-3 space-y-2.5 text-xs pr-1">
                {memoryHistory.length === 0 ? (
                  <div className="text-center py-16 text-slate-500">
                    No past investigation memories recorded.
                  </div>
                ) : (
                  memoryHistory.map((mem) => (
                    <div key={mem.memory_id} className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
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

      {activeReportText && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="max-w-2xl w-full rounded-2xl bg-[#090f1f] border border-cyan-500/50 p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-cyan-400" />
                <h3 className="font-bold text-slate-100 text-sm">
                  Flight-Dynamics Explainability Report
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
