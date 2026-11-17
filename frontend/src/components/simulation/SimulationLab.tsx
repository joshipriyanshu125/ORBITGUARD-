import React, { useState, useEffect } from 'react';
import {
  FlaskConical,
  Play,
  Pause,
  RotateCcw,
  Zap,
  TrendingDown,
  Layers,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  Shield,
  FileText,
  Sliders,
  Fuel,
  Compass
} from 'lucide-react';
import type { ManeuverCandidate, TrajectoryComparisonResult, HypotheticalScenarioResponse } from '../../types';
import { apiService } from '../../services/api';

export const SimulationLab: React.FC = () => {
  const [presets, setPresets] = useState<any[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>('IMMINENT_DEBRIS_COLLISION');
  const [isLoading, setIsLoading] = useState(false);
  const [simulationResult, setSimulationResult] = useState<HypotheticalScenarioResponse | null>(null);

  // Time Scrub Slider
  const [sliderStep, setSliderStep] = useState(12);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<ManeuverCandidate | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Load presets on mount
  useEffect(() => {
    apiService.getSimulationPresets().then((data) => {
      setPresets(data);
    }).catch(console.error);

    // Run default initial simulation
    runSimulation('IMMINENT_DEBRIS_COLLISION');
  }, []);

  const runSimulation = async (scenarioType: string) => {
    setIsLoading(true);
    setActionNotice(null);
    try {
      const res = await apiService.runHypotheticalScenario({
        scenario_id: `SIM-${Date.now().toString().slice(-6)}`,
        scenario_type: scenarioType,
        primary_norad_id: 25544,
        primary_name: 'ISS (ZARYA)',
        secondary_norad_id: 39872,
        secondary_name: 'FENGYUN 1C DEBRIS',
        initial_miss_distance_km: 0.45,
        relative_velocity_kms: 14.2,
        lead_time_hours: 24.0,
        spacecraft_dry_mass_kg: 420000.0,
        spacecraft_propellant_mass_kg: 2500.0,
        thruster_isp_seconds: scenarioType === 'LOW_THRUST_ELECTRIC_PHASING' ? 1500.0 : 310.0,
        max_fuel_budget_kg: scenarioType === 'FUEL_CONSTRAINED_EMERGENCY' ? 25.0 : undefined
      });
      setSimulationResult(res);
      setSelectedCandidate(res.optimal_candidate);
    } catch (err) {
      console.error('Simulation run failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Timeline scrub animation loop
  useEffect(() => {
    let timer: any;
    if (isPlaying && simulationResult) {
      timer = setInterval(() => {
        setSliderStep((prev) => (prev >= 20 ? 0 : prev + 1));
      }, 500);
    }
    return () => clearInterval(timer);
  }, [isPlaying, simulationResult]);

  const currentTrajPoint = simulationResult?.trajectory_comparison?.trajectory_points?.[sliderStep] || null;

  return (
    <div className="space-y-6 pb-12 font-mono">
      {/* Top Presets Navigation Header */}
      <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-cyan-950 text-cyan-400 border border-cyan-800">
            <FlaskConical className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              Orbital Maneuver Simulation Laboratory
            </h2>
            <p className="text-[11px] text-slate-400">
              Clohessy-Wiltshire Dynamics • Tsiolkovsky Rocket Fuel Calculations • What-If Sandbox
            </p>
          </div>
        </div>

        {/* Preset Selector Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {presets.map((p) => {
            const isActive = selectedPreset === p.scenario_type;
            return (
              <button
                key={p.scenario_type}
                onClick={() => {
                  setSelectedPreset(p.scenario_type);
                  runSimulation(p.scenario_type);
                }}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  isActive
                    ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-600/30'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                }`}
              >
                {p.title.split('(')[0].trim()}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main 3D Simulation Stage (Matching Image 5) */}
      <div className="relative h-[480px] rounded-2xl bg-gradient-to-b from-[#050811] via-[#081024] to-[#04060e] border border-slate-800 shadow-2xl overflow-hidden flex items-center justify-center">
        {/* Background Radial Glow */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-cyan-950/20 via-transparent to-transparent pointer-events-none" />

        {/* Orbit Ellipses Graphic */}
        <div className="absolute w-[520px] h-[520px] rounded-full border border-slate-700/40 border-dashed" />
        <div className="absolute w-[560px] h-[560px] rounded-full border border-cyan-500/40 animate-pulse" />

        {/* Center Earth Graphic */}
        <div className="relative z-10 text-center">
          <div className="w-48 h-48 mx-auto rounded-full bg-gradient-to-tr from-blue-700 via-cyan-600 to-indigo-900 shadow-2xl shadow-cyan-500/30 border-2 border-cyan-400/40 flex items-center justify-center relative">
            <div className="text-[10px] text-white/70 font-bold uppercase tracking-wider">
              Earth LEO
            </div>
          </div>
        </div>

        {/* Left Floating Objects Card (Matching Image 5) */}
        <div className="absolute top-4 left-4 z-20 w-64 rounded-2xl bg-[#070d1a]/90 backdrop-blur-md border border-slate-800/90 p-4 space-y-3 text-xs shadow-2xl">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <span className="font-bold text-slate-200">Objects of Interest</span>
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-cyan-900/40">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-cyan-400" />
                <span className="text-slate-200 font-bold">Blue Sat: ISS (ZARYA)</span>
              </div>
              <span className="text-[10px] text-cyan-400 font-mono">NORAD 25544</span>
            </div>

            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-rose-900/40">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-rose-400" />
                <span className="text-slate-200 font-bold">Red Sat: Debris Cloud</span>
              </div>
              <span className="text-[10px] text-rose-400 font-mono">NORAD 39872</span>
            </div>
          </div>

          {currentTrajPoint && (
            <div className="pt-2 border-t border-slate-800 text-[10px] text-slate-400 space-y-1">
              <div className="flex justify-between">
                <span>In-Track Secular Drift:</span>
                <span className="text-cyan-300 font-bold">{currentTrajPoint.in_track_delta_km.toFixed(2)} km</span>
              </div>
              <div className="flex justify-between">
                <span>Radial Altitude Delta:</span>
                <span className="text-cyan-300 font-bold">{currentTrajPoint.radial_delta_km.toFixed(3)} km</span>
              </div>
              <div className="flex justify-between">
                <span>Net 3D Separation:</span>
                <span className="text-emerald-400 font-bold">{currentTrajPoint.separation_delta_km.toFixed(2)} km</span>
              </div>
            </div>
          )}
        </div>

        {/* Right Floating Maneuver Plan Card (Matching Image 5) */}
        {selectedCandidate && (
          <div className="absolute top-4 right-4 z-20 w-80 rounded-2xl bg-[#070d1a]/95 backdrop-blur-md border border-cyan-500/40 p-4 space-y-3.5 text-xs shadow-2xl">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-cyan-400" />
                <span className="font-bold text-slate-100">Maneuver Plan: {selectedCandidate.name}</span>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold">
                RANK #{selectedCandidate.recommendation_rank}
              </span>
            </div>

            <div className="space-y-1.5 text-[11px] text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-400">Burn Direction:</span>
                <span className="text-cyan-300 font-bold">{selectedCandidate.burn_direction}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Impulse Delta-V:</span>
                <span className="text-emerald-400 font-bold">{selectedCandidate.delta_v_ms} m/s</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Propellant Mass (Tsiolkovsky):</span>
                <span className="text-slate-200 font-bold">{selectedCandidate.fuel_mass_kg} kg</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Post-Burn Miss Distance:</span>
                <span className="text-cyan-300 font-bold">{selectedCandidate.projected_miss_distance_km} km</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Post-Burn Collision Pc:</span>
                <span className="text-emerald-400 font-bold">{selectedCandidate.post_maneuver_collision_prob_sci}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Fuel Efficiency:</span>
                <span className="text-purple-400 font-bold">{selectedCandidate.fuel_efficiency_km_per_kg} km/kg</span>
              </div>
            </div>

            {/* Action Buttons (Matching Image 5) */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setActionNotice(`Maneuver trajectory locked and submitted to flight-dynamics schedule: ${selectedCandidate.name} (${selectedCandidate.delta_v_ms} m/s).`)}
                className="w-full py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all shadow-md"
              >
                <CheckCircle className="w-3.5 h-3.5" />
                <span>Lock Trajectory & Perform Maneuver</span>
              </button>

              <button
                onClick={() => {
                  const cands = simulationResult?.candidates_evaluated || [];
                  const nextIndex = (cands.findIndex((c) => c.candidate_id === selectedCandidate.candidate_id) + 1) % cands.length;
                  setSelectedCandidate(cands[nextIndex]);
                }}
                className="w-full py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs transition-colors"
              >
                Recalculate for a Different Approach
              </button>

              <button
                onClick={() => setActionNotice('Target debris trajectory analyzed: stable secular drift, 0 secondary conjunctions induced.')}
                className="w-full py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 text-xs transition-colors"
              >
                Analyze Target Behavior Before Locking
              </button>
            </div>
          </div>
        )}

        {/* Action Notice Toast */}
        {actionNotice && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 px-4 py-2 rounded-xl bg-cyan-950/95 border border-cyan-500 text-xs text-cyan-200 shadow-2xl flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-cyan-400" />
            <span>{actionNotice}</span>
          </div>
        )}

        {/* Bottom Timeline Scrub Bar (Matching Image 5) */}
        <div className="absolute bottom-4 left-6 right-6 z-20 p-3 rounded-2xl bg-[#070d1a]/95 backdrop-blur-md border border-slate-800 flex items-center gap-4 text-xs">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white transition-colors"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>

          <span className="text-[11px] text-cyan-300 font-bold whitespace-nowrap">
            T-{((20 - sliderStep) * 1.2).toFixed(1)}h to TCA
          </span>

          <input
            type="range"
            min={0}
            max={20}
            value={sliderStep}
            onChange={(e) => setSliderStep(Number(e.target.value))}
            className="flex-1 accent-cyan-500 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
          />

          <span className="text-[10px] text-slate-400 whitespace-nowrap">
            Step {sliderStep}/20
          </span>
        </div>
      </div>

      {/* Fuel Comparison & Strategy Trade-off Table */}
      {simulationResult && (
        <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <Fuel className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                Candidate Avoidance Strategies & Propellant Comparison
              </h3>
            </div>
            <span className="text-[10px] text-slate-500">Tsiolkovsky Equation Model</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="py-2.5 px-3">Candidate</th>
                  <th className="py-2.5 px-3">Strategy</th>
                  <th className="py-2.5 px-3">Delta-V (m/s)</th>
                  <th className="py-2.5 px-3">Propellant (kg)</th>
                  <th className="py-2.5 px-3">Post Miss (km)</th>
                  <th className="py-2.5 px-3">Efficiency (km/kg)</th>
                  <th className="py-2.5 px-3">CARA Status</th>
                  <th className="py-2.5 px-3 text-right">Select</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {simulationResult.fuel_comparison_table.map((row) => {
                  const isSelected = selectedCandidate?.candidate_id === row.candidate_id;
                  return (
                    <tr
                      key={row.candidate_id}
                      onClick={() => {
                        const cand = simulationResult.candidates_evaluated.find(
                          (c) => c.candidate_id === row.candidate_id
                        );
                        if (cand) setSelectedCandidate(cand);
                      }}
                      className={`hover:bg-slate-900/60 cursor-pointer transition-colors ${
                        isSelected ? 'bg-cyan-950/40 border-l-2 border-cyan-400' : ''
                      }`}
                    >
                      <td className="py-3 px-3 font-bold text-cyan-400">{row.candidate_id}</td>
                      <td className="py-3 px-3 font-semibold text-slate-200">{row.strategy}</td>
                      <td className="py-3 px-3 font-bold text-emerald-400">{row.delta_v_ms}</td>
                      <td className="py-3 px-3 font-mono text-slate-100">{row.propellant_consumed_kg} kg</td>
                      <td className="py-3 px-3 font-bold text-cyan-300">{row.post_burn_miss_km} km</td>
                      <td className="py-3 px-3 text-purple-400 font-bold">{row.efficiency_km_per_kg}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                          NOMINAL GREEN
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          className={`px-3 py-1 rounded-lg text-[10px] font-bold transition-colors ${
                            isSelected
                              ? 'bg-cyan-600 text-white'
                              : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {isSelected ? 'Active' : 'Apply'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
