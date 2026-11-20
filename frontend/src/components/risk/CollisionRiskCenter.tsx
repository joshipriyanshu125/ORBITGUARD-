import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertOctagon,
  FileText,
  Radar,
  RefreshCw,
  Satellite as SatelliteIcon,
  ChevronRight
} from 'lucide-react';
import type { ConjunctionSummary, SatelliteSummary } from '../../types';
import { apiService } from '../../services/api';

interface CollisionRiskCenterProps {
  conjunctions: ConjunctionSummary[];
  satellites: SatelliteSummary[];
  onSelectConjunctionForSimulation?: (conjunction: ConjunctionSummary) => void;
  onRefresh: () => Promise<void>;
}

const formatUtc = (value?: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.toISOString().replace('T', ' ').slice(0, 19)} UTC`;
};

const tierStyle = (tier?: string) => {
  switch (tier) {
    case 'CRITICAL': return 'bg-rose-950 text-rose-300 border-rose-800';
    case 'HIGH': return 'bg-orange-950 text-orange-300 border-orange-800';
    case 'MEDIUM': return 'bg-amber-950 text-amber-300 border-amber-800';
    default: return 'bg-slate-900 text-slate-400 border-slate-700';
  }
};

const formatReport = (eventId: string, conj: ConjunctionSummary, report: any) => {
  const lines = [
    `COLLISION RISK ASSESSMENT & EXPLAINABILITY REPORT [${eventId}]`,
    `Primary: ${conj.primary_name} (NORAD ${conj.primary_norad_id}) vs Secondary: ${conj.secondary_name} (NORAD ${conj.secondary_norad_id})`,
    `TCA: ${formatUtc(conj.tca)} | Miss: ${conj.miss_distance_km.toFixed(3)} km | Rel. velocity: ${conj.relative_speed_kms.toFixed(2)} km/s`,
    '',
    `Executive Summary: ${report.executive_summary}`,
    '',
    `Physical Geometry: ${report.geometry_explanation}`,
    '',
    `Uncertainty Breakdown: ${report.uncertainty_explanation}`,
    '',
    `Probabilistic CARA Risk: ${report.probabilistic_explanation}`,
    '',
    `Human-in-the-Loop Directive: ${report.hitl_recommendation}`
  ];
  return lines.join('\n');
};

export const CollisionRiskCenter: React.FC<CollisionRiskCenterProps> = ({
  conjunctions,
  satellites,
  onSelectConjunctionForSimulation,
  onRefresh
}) => {
  const [selectedConjunction, setSelectedConjunction] = useState<ConjunctionSummary | null>(null);
  const [reportText, setReportText] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);

  const [screenNoradId, setScreenNoradId] = useState<string>('');
  const [isScreening, setIsScreening] = useState(false);
  const [screenMessage, setScreenMessage] = useState<string | null>(null);

  useEffect(() => {
    setSelectedConjunction((prev) => {
      if (prev && conjunctions.some((c) => c.conjunction_id === prev.conjunction_id)) return prev;
      return conjunctions[0] ?? null;
    });
  }, [conjunctions]);

  useEffect(() => {
    if (!screenNoradId && satellites.length > 0) {
      setScreenNoradId(String(satellites[0].norad_id));
    }
  }, [satellites, screenNoradId]);

  const highRiskCount = conjunctions.filter(
    (c) => c.risk_tier === 'CRITICAL' || c.risk_tier === 'HIGH'
  ).length;

  const earliest = useMemo(() => {
    if (conjunctions.length === 0) return null;
    return [...conjunctions].sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime())[0];
  }, [conjunctions]);

  const closest = useMemo(() => {
    if (conjunctions.length === 0) return null;
    return [...conjunctions].sort((a, b) => a.miss_distance_km - b.miss_distance_km)[0];
  }, [conjunctions]);

  const handleScreening = async () => {
    setIsScreening(true);
    setScreenMessage(null);
    try {
      const result = await apiService.screenConjunctions({ primary_norad_id: Number(screenNoradId) });
      setScreenMessage(
        `Screened ${result.candidates_screened ?? 0} candidates for ${result.primary_name ?? screenNoradId}: ` +
        `${result.conjunctions_detected ?? 0} conjunction(s) detected.`
      );
      await onRefresh();
    } catch (err: any) {
      setScreenMessage(err?.response?.data?.detail || 'Conjunction screening failed.');
    } finally {
      setIsScreening(false);
    }
  };

  const handleGenerateReport = async (conj: ConjunctionSummary) => {
    setIsLoadingReport(true);
    setReportError(null);
    try {
      const report = await apiService.getCollisionReport(conj.conjunction_id);
      setReportText(formatReport(conj.conjunction_id, conj, report));
    } catch (err: any) {
      setReportText(null);
      setReportError(err?.response?.data?.detail || 'Explainability report is unavailable for this event.');
    } finally {
      setIsLoadingReport(false);
    }
  };

  return (
    <div className="space-y-6 pb-12 font-mono">
      {/* Real stored-event metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Stored Conjunctions</span>
          <div className="text-2xl font-black text-slate-100 mt-1">{conjunctions.length}</div>
          <span className="text-[11px] text-cyan-400 mt-2 block">From catalog screening</span>
        </div>

        <div className="p-4 rounded-2xl bg-[#090f1d] border border-amber-500/30 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">High / Critical Risk</span>
          <div className={`text-2xl font-black mt-1 ${highRiskCount > 0 ? 'text-rose-400' : 'text-slate-300'}`}>
            {highRiskCount}
          </div>
          <span className="text-[11px] text-slate-400 mt-2 block">Risk tier HIGH or CRITICAL</span>
        </div>

        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Earliest TCA</span>
          <div className="text-sm font-bold text-slate-200 mt-2">
            {earliest ? formatUtc(earliest.tca) : 'No events'}
          </div>
          <span className="text-[10px] text-slate-500 mt-2 block truncate">
            {earliest ? earliest.conjunction_id : '—'}
          </span>
        </div>

        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Closest Approach</span>
          <div className="text-2xl font-black text-cyan-300 mt-1">
            {closest ? `${closest.miss_distance_km.toFixed(2)} km` : '—'}
          </div>
          <span className="text-[10px] text-slate-500 mt-2 block truncate">
            {closest ? `${closest.primary_name} vs ${closest.secondary_name}` : 'No events'}
          </span>
        </div>
      </div>

      {/* Screening control */}
      <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
          <Radar className="w-4 h-4 text-cyan-400" />
          Screen close approaches
        </div>
        <select
          value={screenNoradId}
          onChange={(e) => setScreenNoradId(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 min-w-56"
        >
          {satellites.length === 0 && <option value="">Catalog is empty</option>}
          {satellites.map((sat) => (
            <option key={sat.norad_id} value={sat.norad_id}>
              {sat.name} (NORAD {sat.norad_id})
            </option>
          ))}
        </select>
        <button
          onClick={handleScreening}
          disabled={isScreening || !screenNoradId}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white text-xs font-bold"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isScreening ? 'animate-spin' : ''}`} />
          {isScreening ? 'Screening…' : 'Run screening'}
        </button>
        {screenMessage && <span className="text-[11px] text-slate-400">{screenMessage}</span>}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Event table */}
        <div className="xl:col-span-2 p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-rose-400" />
              <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                Stored Conjunction Events
              </h3>
            </div>
            <span className="text-[10px] text-slate-500">SGP4 screened catalog events</span>
          </div>

          {conjunctions.length === 0 ? (
            <div className="py-14 text-center text-xs text-slate-500 space-y-2">
              <SatelliteIcon className="w-8 h-8 text-slate-700 mx-auto" />
              <p>No conjunction events are stored.</p>
              <p className="text-[10px]">Sync the catalog, then run screening for a real catalog object above.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="py-2.5 px-3">Event</th>
                    <th className="py-2.5 px-3">Primary vs Secondary</th>
                    <th className="py-2.5 px-3">TCA</th>
                    <th className="py-2.5 px-3">Miss (km)</th>
                    <th className="py-2.5 px-3">Rel V (km/s)</th>
                    <th className="py-2.5 px-3">Risk</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {conjunctions.map((conj) => (
                    <tr
                      key={conj.conjunction_id}
                      onClick={() => setSelectedConjunction(conj)}
                      className={`hover:bg-slate-900/60 cursor-pointer transition-colors ${
                        selectedConjunction?.conjunction_id === conj.conjunction_id
                          ? 'bg-cyan-950/40 border-l-2 border-cyan-400'
                          : ''
                      }`}
                    >
                      <td className="py-3 px-3 font-bold text-cyan-400">{conj.conjunction_id}</td>
                      <td className="py-3 px-3">
                        <span className="text-slate-200 font-semibold">{conj.primary_name}</span>
                        <span className="text-slate-500 block text-[10px]">vs {conj.secondary_name}</span>
                      </td>
                      <td className="py-3 px-3 text-slate-400">{formatUtc(conj.tca)}</td>
                      <td className="py-3 px-3 font-bold text-slate-100">{conj.miss_distance_km.toFixed(2)}</td>
                      <td className="py-3 px-3">{conj.relative_speed_kms.toFixed(1)}</td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${tierStyle(conj.risk_tier)}`}>
                          {conj.risk_tier ?? 'UNKNOWN'}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleGenerateReport(conj);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 text-[10px] font-bold transition-colors mr-1.5"
                        >
                          Report
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectConjunctionForSimulation?.(conj);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-800 text-cyan-300 text-[10px] font-bold transition-colors"
                        >
                          Simulate
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {reportError && <p className="text-[11px] text-rose-400">{reportError}</p>}
        </div>

        {/* Selected event details */}
        <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl space-y-4">
          <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <FileText className="w-4 h-4 text-cyan-400" />
            Event Detail
          </h3>

          {!selectedConjunction ? (
            <p className="text-xs text-slate-500 py-8 text-center">
              Select a stored conjunction to inspect its real catalog-derived geometry.
            </p>
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
                  ['Risk Tier', selectedConjunction.risk_tier ?? 'UNKNOWN'],
                  ['Risk Score', selectedConjunction.risk_score != null ? selectedConjunction.risk_score.toFixed(1) : '—'],
                  ['Status', selectedConjunction.status ?? '—']
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between gap-3 border-b border-slate-800/50 py-1">
                    <span className="text-slate-500">{label}</span>
                    <span className="text-slate-200 text-right break-all">{value}</span>
                  </div>
                ))}
              </div>

              <button
                onClick={() => handleGenerateReport(selectedConjunction)}
                disabled={isLoadingReport}
                className="w-full py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-bold flex items-center justify-center gap-2"
              >
                <FileText className="w-3.5 h-3.5" />
                {isLoadingReport ? 'Synthesizing…' : 'Synthesize report from catalog TLEs'}
              </button>

              {onSelectConjunctionForSimulation && (
                <button
                  onClick={() => onSelectConjunctionForSimulation(selectedConjunction)}
                  className="w-full py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-bold flex items-center justify-center gap-2"
                >
                  Open in Simulation Lab
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Report modal */}
      {reportText && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="max-w-2xl w-full rounded-2xl bg-[#090f1f] border border-cyan-500/50 p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-cyan-400" />
                <h3 className="font-bold text-slate-100 text-sm">
                  Collision Assessment & Explainability Report
                </h3>
              </div>
              <button onClick={() => setReportText(null)} className="text-slate-400 hover:text-white text-sm">
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
              {reportText}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setReportText(null)}
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
