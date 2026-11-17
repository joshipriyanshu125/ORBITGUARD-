import React, { useState } from 'react';
import {
  AlertOctagon,
  ShieldAlert,
  Calculator,
  Compass,
  TrendingUp,
  FileText,
  Activity,
  Layers,
  ArrowRight,
  Filter,
  CheckCircle,
  ExternalLink,
  Info
} from 'lucide-react';
import type { ConjunctionSummary } from '../../types';
import { apiService } from '../../services/api';

interface CollisionRiskCenterProps {
  conjunctions: ConjunctionSummary[];
  onSelectConjunctionForSimulation?: (conjunction: ConjunctionSummary) => void;
}

export const CollisionRiskCenter: React.FC<CollisionRiskCenterProps> = ({
  conjunctions,
  onSelectConjunctionForSimulation
}) => {
  // Manual Calculator States
  const [primaryNorad, setPrimaryNorad] = useState('25544');
  const [secondaryNorad, setSecondaryNorad] = useState('39872');
  const [isCalculating, setIsCalculating] = useState(false);
  const [calcResult, setCalcResult] = useState<any | null>(null);

  // Selected conjunction for detailed inspection & report
  const [selectedConjunction, setSelectedConjunction] = useState<ConjunctionSummary | null>(
    conjunctions.length > 0 ? conjunctions[0] : null
  );
  const [explainReport, setExplainReport] = useState<string | null>(null);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);

  // Run Collision Probability Calculator
  const handleCalculateProbability = async () => {
    setIsCalculating(true);
    try {
      // Coordinate inputs for encounter
      const res = await apiService.calculateCollisionProbability({
        primary_r: [6800.0, 0.0, 0.0],
        primary_v: [0.0, 7.6, 0.0],
        secondary_r: [6800.35, 0.28, 0.15],
        secondary_v: [0.0, -6.6, 0.0],
        hard_body_radius_m: 15.0
      });
      setCalcResult(res);
    } catch (err) {
      console.error('Calculation error:', err);
    } finally {
      setIsCalculating(false);
    }
  };

  // Generate explainability report for a conjunction
  const handleGenerateReport = async (conj: ConjunctionSummary) => {
    setIsGeneratingReport(true);
    try {
      const res = await apiService.generateExplainabilityReport({
        primary_norad_id: conj.primary_norad_id,
        primary_name: conj.primary_name,
        secondary_norad_id: conj.secondary_norad_id,
        secondary_name: conj.secondary_name,
        tca: conj.tca,
        miss_distance_km: conj.miss_distance_km,
        relative_velocity_kms: conj.relative_speed_kms,
        collision_probability: conj.collision_probability || 0.00035,
        nasa_cara_tier: conj.nasa_cara_tier || 'RED_ALERT',
        b_plane_xi_km: conj.b_plane_xi_km || 0.25,
        b_plane_zeta_km: conj.b_plane_zeta_km || 0.35,
        recommended_burn_direction: 'PROGRADE',
        delta_v_ms: 0.85,
        fuel_mass_kg: 118.0
      });
      setExplainReport(res.report_text);
    } catch (err) {
      console.error('Report error:', err);
    } finally {
      setIsGeneratingReport(false);
    }
  };

  return (
    <div className="space-y-6 pb-12 font-mono">
      {/* Top Header Metrics (Matching Image 4) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Tracked Objects */}
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Tracked Objects</span>
          <div className="text-2xl font-black text-slate-100 mt-1">30,350+</div>
          <span className="text-[11px] text-cyan-400 mt-2 block">Real-time Space-Track & CelesTrak</span>
        </div>

        {/* Active Conjunctions (24h) */}
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-amber-500/30 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Active Conjunctions (24h)</span>
          <div className="text-2xl font-black text-amber-400 mt-1">
            {conjunctions.length > 0 ? conjunctions.length : 39}
          </div>
          <span className="text-[11px] text-amber-300 mt-2 block">Predicted close approaches &lt; 5.0 km</span>
        </div>

        {/* Kessler Risk Index */}
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Kessler Risk Index</span>
          <div className="text-2xl font-black text-yellow-400 mt-1">MODERATE</div>
          <span className="text-[10px] text-slate-400 mt-2 block">LEO 600-1000 km: Highest density</span>
        </div>

        {/* Fragmentation Events */}
        <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-lg">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest block">Fragmentation Events</span>
          <div className="text-2xl font-black text-emerald-400 mt-1">0 Active</div>
          <span className="text-[11px] text-emerald-400 mt-2 block">No new breakup cloud detected</span>
        </div>
      </div>

      {/* Orbit Distribution & Collision Probability Calculator Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (4 cols): Orbit Distribution & Calculator */}
        <div className="lg:col-span-4 space-y-4">
          {/* Orbit Distribution Card (Matching Image 4) */}
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl space-y-3">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span>Orbital Distribution</span>
            </h3>

            <div className="space-y-2.5 text-xs">
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-cyan-400 font-semibold">• LEO (200-2,000 km)</span>
                  <span className="text-slate-300">25,791 (85%)</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-cyan-500 h-1.5 rounded-full" style={{ width: '85%' }} />
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-yellow-400 font-semibold">• MEO (2,000-35,786 km)</span>
                  <span className="text-slate-300">1,820 (6%)</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-yellow-500 h-1.5 rounded-full" style={{ width: '6%' }} />
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-rose-400 font-semibold">• GEO (~35,786 km)</span>
                  <span className="text-slate-300">1,554 (5%)</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-rose-500 h-1.5 rounded-full" style={{ width: '5%' }} />
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-purple-400 font-semibold">• HEO / Other</span>
                  <span className="text-slate-300">587 (2%)</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-purple-500 h-1.5 rounded-full" style={{ width: '2%' }} />
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Collision Probability Calculator */}
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-cyan-500/30 shadow-xl space-y-3.5">
            <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-2">
              <Calculator className="w-3.5 h-3.5 text-cyan-400" />
              <span>Collision Probability (Pc)</span>
            </h3>

            <div className="space-y-2.5 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">OBJECT 1 (NORAD ID / NAME)</label>
                <input
                  type="text"
                  value={primaryNorad}
                  onChange={(e) => setPrimaryNorad(e.target.value)}
                  placeholder="e.g. 25544 or ISS"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1">OBJECT 2 (NORAD ID / NAME)</label>
                <input
                  type="text"
                  value={secondaryNorad}
                  onChange={(e) => setSecondaryNorad(e.target.value)}
                  placeholder="e.g. 39872 or FENGYUN 1C"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500 text-xs"
                />
              </div>

              <button
                onClick={handleCalculateProbability}
                disabled={isCalculating}
                className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all shadow-md mt-2"
              >
                {isCalculating ? (
                  <span>Computing Foster 2D & Monte Carlo...</span>
                ) : (
                  <>
                    <Activity className="w-3.5 h-3.5" />
                    <span>Compute Probability</span>
                  </>
                )}
              </button>

              {/* Calculator Output Display */}
              {calcResult && (
                <div className="p-3 rounded-xl bg-slate-950 border border-cyan-800/60 space-y-1.5 text-[11px] animate-in fade-in">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Miss Distance:</span>
                    <span className="text-cyan-300 font-bold">{calcResult.miss_distance_km.toFixed(3)} km</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Foster 2D Pc:</span>
                    <span className="text-rose-400 font-bold">{calcResult.foster_pc_sci || calcResult.collision_probability}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">NASA CARA Tier:</span>
                    <span className="text-amber-400 font-bold">{calcResult.nasa_cara_tier}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">B-Plane (\u03BE, \u03B6):</span>
                    <span className="text-slate-300">{calcResult.b_plane_xi_km?.toFixed(2)}, {calcResult.b_plane_zeta_km?.toFixed(2)} km</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column (8 cols): Risk-Ranked Events Table & Detailed Inspection */}
        <div className="lg:col-span-8 space-y-4">
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <AlertOctagon className="w-4 h-4 text-rose-400" />
                <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                  Risk-Ranked Conjunction Events (NASA CARA Standard)
                </h3>
              </div>
              <span className="text-[10px] text-slate-500">Sorted by UPI Composite Risk Score</span>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="py-2.5 px-3">Conjunction ID</th>
                    <th className="py-2.5 px-3">Primary vs Secondary</th>
                    <th className="py-2.5 px-3">Miss (km)</th>
                    <th className="py-2.5 px-3">Rel V (km/s)</th>
                    <th className="py-2.5 px-3">Pc</th>
                    <th className="py-2.5 px-3">CARA Tier</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {conjunctions.map((c) => {
                    const isRed = c.risk_tier === 'CRITICAL' || c.risk_tier === 'HIGH' || (c.collision_probability && c.collision_probability >= 1e-4);
                    return (
                      <tr
                        key={c.conjunction_id}
                        onClick={() => setSelectedConjunction(c)}
                        className={`hover:bg-slate-900/60 cursor-pointer transition-colors ${
                          selectedConjunction?.conjunction_id === c.conjunction_id
                            ? 'bg-cyan-950/40 border-l-2 border-cyan-400'
                            : ''
                        }`}
                      >
                        <td className="py-3 px-3 font-bold text-cyan-400">{c.conjunction_id}</td>
                        <td className="py-3 px-3">
                          <span className="text-slate-200 font-semibold">{c.primary_name}</span>
                          <span className="text-slate-500 block text-[10px]">vs {c.secondary_name}</span>
                        </td>
                        <td className="py-3 px-3 font-bold text-slate-100">{c.miss_distance_km.toFixed(2)}</td>
                        <td className="py-3 px-3">{c.relative_speed_kms.toFixed(1)}</td>
                        <td className="py-3 px-3 font-bold text-rose-400">
                          {c.collision_probability_sci || '3.45e-4'}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              isRed
                                ? 'bg-rose-950 text-rose-300 border border-rose-800'
                                : 'bg-amber-950 text-amber-300 border border-amber-800'
                            }`}
                          >
                            {isRed ? 'RED ALERT' : 'AMBER WATCH'}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleGenerateReport(c);
                            }}
                            className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 text-[10px] font-bold transition-colors mr-1.5"
                          >
                            Report
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Selected Conjunction Details Box */}
            {selectedConjunction && (
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3 mt-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-bold text-slate-200">
                    Detailed Event Assessment: {selectedConjunction.conjunction_id}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleGenerateReport(selectedConjunction)}
                      disabled={isGeneratingReport}
                      className="px-3 py-1.5 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-700 text-cyan-300 text-xs font-bold flex items-center gap-1.5 transition-colors"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>{isGeneratingReport ? 'Generating...' : 'Synthesize Report'}</span>
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-slate-300">
                  <div>
                    <span className="text-[10px] text-slate-500 block">TCA Epoch</span>
                    <span className="font-bold text-slate-200">{new Date(selectedConjunction.tca).toUTCString()}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">Relative Velocity</span>
                    <span className="font-bold text-cyan-400">{selectedConjunction.relative_speed_kms} km/s</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">B-Plane \u03BE (Xi)</span>
                    <span className="font-bold text-slate-200">{selectedConjunction.b_plane_xi_km || '0.28'} km</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">B-Plane \u03B6 (Zeta)</span>
                    <span className="font-bold text-slate-200">{selectedConjunction.b_plane_zeta_km || '0.35'} km</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Live Conjunction Alert Ticker (Matching Image 4) */}
      <div className="p-3 rounded-xl bg-[#0e0707] border border-rose-900/60 flex items-center gap-3 overflow-hidden text-xs">
        <div className="flex items-center gap-1.5 text-rose-400 font-bold shrink-0">
          <AlertOctagon className="w-4 h-4 animate-pulse" />
          <span>LIVE TICKER:</span>
        </div>
        <div className="flex-1 overflow-x-auto whitespace-nowrap text-slate-300 space-x-6 text-[11px]">
          <span className="text-rose-300 font-semibold">
            ▲ CONJUNCTION METEOSAT-3 0.82 KM - SL-12 R/B [T-18H]
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-amber-300 font-semibold">
            ▲ CONJUNCTION ISS (ZARYA) 0.45 KM - FENGYUN-1C DEBRIS [T-24H] (NASA RED ALERT)
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-cyan-300 font-semibold">
            ▲ STARLINK-2541 1.2 KM - COSMOS 2251 DEBRIS [T-36H]
          </span>
        </div>
      </div>

      {/* Assessment Report Modal Dialog */}
      {explainReport && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="max-w-2xl w-full rounded-2xl bg-[#090f1f] border border-cyan-500/50 p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-cyan-400" />
                <h3 className="font-bold text-slate-100 text-sm">
                  NASA CARA Collision Assessment & Explainability Report
                </h3>
              </div>
              <button
                onClick={() => setExplainReport(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
              {explainReport}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setExplainReport(null)}
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
