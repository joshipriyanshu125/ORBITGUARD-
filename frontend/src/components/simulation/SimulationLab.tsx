import React, { useEffect, useMemo, useState } from 'react';
import {
  FlaskConical,
  Play,
  Pause,
  AlertTriangle,
  CheckCircle,
  Fuel,
  ShieldAlert
} from 'lucide-react';
import type {
  ConjunctionSummary,
  SatelliteSummary,
  ManeuverCandidate,
  HypotheticalScenarioResponse
} from '../../types';
import { apiService } from '../../services/api';

interface SimulationLabProps {
  satellites: SatelliteSummary[];
  conjunctions: ConjunctionSummary[];
  initialConjunction?: ConjunctionSummary | null;
}

const SCENARIO_TYPES = [
  { value: 'IMMINENT_DEBRIS_COLLISION', label: 'Imminent Close Approach' },
  { value: 'FUEL_CONSTRAINED_EMERGENCY', label: 'Propellant-Constrained Avoidance' },
  { value: 'LOW_THRUST_ELECTRIC_PHASING', label: 'Low-Thrust Electric Phasing' },
  { value: 'SECONDARY_CONJUNCTION_HAZARD', label: 'Secondary Conjunction Hazard' }
];

const leadTimeHours = (tca: string) => {
  const ms = new Date(tca).getTime() - Date.now();
  return Math.max(1, Math.round((ms / 3600000) * 10) / 10);
};

export const SimulationLab: React.FC<SimulationLabProps> = ({
  satellites,
  conjunctions,
  initialConjunction
}) => {
  const [conjunctionId, setConjunctionId] = useState<string>('');
  const [scenarioType, setScenarioType] = useState('IMMINENT_DEBRIS_COLLISION');

  const [missDistance, setMissDistance] = useState('');
  const [relativeVelocity, setRelativeVelocity] = useState('');
  const [semiMajorAxis, setSemiMajorAxis] = useState('');
  const [dryMass, setDryMass] = useState('');
  const [propellantMass, setPropellantMass] = useState('');
  const [isp, setIsp] = useState('');
  const [maxFuelBudget, setMaxFuelBudget] = useState('');

  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<HypotheticalScenarioResponse | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<ManeuverCandidate | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [pointIndex, setPointIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const selectedConjunction = useMemo(
    () => conjunctions.find((c) => c.conjunction_id === conjunctionId) ?? null,
    [conjunctions, conjunctionId]
  );

  // Prefill only real values: conjunction geometry and catalog orbital elements.
  useEffect(() => {
    const conj = initialConjunction
      ? conjunctions.find((c) => c.conjunction_id === initialConjunction.conjunction_id) ?? initialConjunction
      : null;
    if (conj) setConjunctionId(conj.conjunction_id);
  }, [initialConjunction, conjunctions]);

  useEffect(() => {
    if (!selectedConjunction) return;
    setMissDistance(String(selectedConjunction.miss_distance_km));
    setRelativeVelocity(String(selectedConjunction.relative_speed_kms));
    const primary = satellites.find((s) => s.norad_id === selectedConjunction.primary_norad_id);
    setSemiMajorAxis(primary?.semi_major_axis_km != null ? String(primary.semi_major_axis_km) : '');
    setResult(null);
    setSelectedCandidate(null);
    setError(null);
  }, [selectedConjunction, satellites]);

  const trajectoryPoints = result?.trajectory_comparison.trajectory_points ?? [];
  const currentPoint = trajectoryPoints[pointIndex] ?? null;

  useEffect(() => {
    if (!isPlaying || trajectoryPoints.length === 0) return;
    const timer = setInterval(() => {
      setPointIndex((prev) => (prev + 1) % trajectoryPoints.length);
    }, 500);
    return () => clearInterval(timer);
  }, [isPlaying, trajectoryPoints.length]);

  const missingInputs = !selectedConjunction ||
    !missDistance || !relativeVelocity || !semiMajorAxis ||
    !dryMass || !propellantMass || !isp;

  const handleRun = async () => {
    if (!selectedConjunction) return;
    setIsRunning(true);
    setError(null);
    setResult(null);
    setSelectedCandidate(null);
    try {
      const res = await apiService.runHypotheticalScenario({
        scenario_id: `SIM-${Date.now().toString().slice(-6)}`,
        scenario_type: scenarioType,
        primary_norad_id: selectedConjunction.primary_norad_id,
        primary_name: selectedConjunction.primary_name,
        secondary_norad_id: selectedConjunction.secondary_norad_id,
        secondary_name: selectedConjunction.secondary_name,
        semi_major_axis_km: Number(semiMajorAxis),
        initial_miss_distance_km: Number(missDistance),
        relative_velocity_kms: Number(relativeVelocity),
        lead_time_hours: leadTimeHours(selectedConjunction.tca),
        spacecraft_dry_mass_kg: Number(dryMass),
        spacecraft_propellant_mass_kg: Number(propellantMass),
        thruster_isp_seconds: Number(isp),
        max_fuel_budget_kg:
          scenarioType === 'FUEL_CONSTRAINED_EMERGENCY' && maxFuelBudget
            ? Number(maxFuelBudget)
            : undefined
      });
      setResult(res);
      setSelectedCandidate(res.optimal_candidate);
      setPointIndex(0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Simulation request failed.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6 pb-12 font-mono">
      <div className="p-4 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl flex items-center gap-3">
        <div className="p-2 rounded-xl bg-cyan-950 text-cyan-400 border border-cyan-800">
          <FlaskConical className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Orbital Maneuver Simulation Laboratory
          </h2>
          <p className="text-[11px] text-slate-400">
            Clohessy-Wiltshire relative motion and Tsiolkovsky propellant accounting.
            Analytical only; no maneuver is proposed or uplinked from this page.
          </p>
        </div>
      </div>

      {/* Scenario input form */}
      <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl space-y-4">
        <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
          Scenario Inputs
        </h3>

        {conjunctions.length === 0 ? (
          <div className="py-10 text-center text-xs text-slate-500 space-y-2">
            <AlertTriangle className="w-8 h-8 text-slate-700 mx-auto" />
            <p>No stored conjunction is available to simulate.</p>
            <p className="text-[10px]">Run conjunction screening in the Collision Risk Center first.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
              <label className="space-y-1 block">
                <span className="text-[10px] text-slate-400 uppercase">Conjunction Event</span>
                <select
                  value={conjunctionId}
                  onChange={(e) => setConjunctionId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="">Select a stored conjunction…</option>
                  {conjunctions.map((c) => (
                    <option key={c.conjunction_id} value={c.conjunction_id}>
                      {c.conjunction_id} — {c.primary_name} vs {c.secondary_name} ({c.miss_distance_km.toFixed(2)} km)
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1 block">
                <span className="text-[10px] text-slate-400 uppercase">Scenario Type</span>
                <select
                  value={scenarioType}
                  onChange={(e) => setScenarioType(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  {SCENARIO_TYPES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </label>
            </div>

            {selectedConjunction && (
              <div className="rounded-xl bg-slate-950/70 border border-slate-800 p-3 text-[11px] grid grid-cols-2 md:grid-cols-4 gap-2">
                <div><span className="text-slate-500 block">Primary</span><span className="text-slate-200">{selectedConjunction.primary_name} ({selectedConjunction.primary_norad_id})</span></div>
                <div><span className="text-slate-500 block">Secondary</span><span className="text-slate-200">{selectedConjunction.secondary_name} ({selectedConjunction.secondary_norad_id})</span></div>
                <div><span className="text-slate-500 block">TCA</span><span className="text-slate-200">{new Date(selectedConjunction.tca).toUTCString()}</span></div>
                <div><span className="text-slate-500 block">Lead Time</span><span className="text-slate-200">{leadTimeHours(selectedConjunction.tca)} h</span></div>
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              {[
                { label: 'Miss Distance (km)', value: missDistance, set: setMissDistance },
                { label: 'Relative Velocity (km/s)', value: relativeVelocity, set: setRelativeVelocity },
                { label: 'Semi-Major Axis (km)', value: semiMajorAxis, set: setSemiMajorAxis },
                { label: 'Spacecraft Dry Mass (kg)', value: dryMass, set: setDryMass },
                { label: 'Propellant Mass (kg)', value: propellantMass, set: setPropellantMass },
                { label: 'Thruster Isp (s)', value: isp, set: setIsp },
                ...(scenarioType === 'FUEL_CONSTRAINED_EMERGENCY'
                  ? [{ label: 'Max Fuel Budget (kg)', value: maxFuelBudget, set: setMaxFuelBudget }]
                  : [])
              ].map((field) => (
                <label key={field.label} className="space-y-1 block">
                  <span className="text-[10px] text-slate-400 uppercase">{field.label}</span>
                  <input
                    type="number"
                    min="0"
                    value={field.value}
                    onChange={(e) => field.set(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                </label>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleRun}
                disabled={isRunning || missingInputs}
                className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white text-xs font-bold flex items-center gap-2"
              >
                <Play className="w-3.5 h-3.5" />
                {isRunning ? 'Running simulation…' : 'Run simulation'}
              </button>
              <span className="text-[10px] text-slate-500">
                Spacecraft mass, propellant, Isp and semi-major axis are operator-supplied; no defaults are assumed.
              </span>
            </div>

            {error && <p className="text-[11px] text-rose-400">{error}</p>}
          </>
        )}
      </div>

      {result && selectedCandidate && (
        <>
          {/* Optimal candidate + secondary risk */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 p-5 rounded-2xl bg-[#090f1d] border border-cyan-500/40 shadow-xl space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                  Selected Maneuver: {selectedCandidate.name}
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold">
                  RANK #{selectedCandidate.recommendation_rank}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-[11px]">
                {[
                  ['Burn Direction', selectedCandidate.burn_direction],
                  ['Delta-V', `${selectedCandidate.delta_v_ms} m/s`],
                  ['Propellant', `${selectedCandidate.fuel_mass_kg} kg`],
                  ['Post-Burn Miss', `${selectedCandidate.projected_miss_distance_km} km`],
                  ['Post-Burn Pc', selectedCandidate.post_maneuver_collision_prob_sci],
                  ['CARA Tier', selectedCandidate.post_maneuver_cara_tier],
                  ['Efficiency', `${selectedCandidate.fuel_efficiency_km_per_kg} km/kg`],
                  ['Residual Propellant', `${selectedCandidate.residual_fuel_budget_kg} kg`],
                  ['Lead Time to TCA', `${selectedCandidate.lead_time_to_tca_hours} h`]
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between gap-2 border-b border-slate-800/50 py-1">
                    <span className="text-slate-500">{label}</span>
                    <span className="text-slate-200 text-right">{value}</span>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-slate-500">{selectedCandidate.tradeoff_rationale}</p>
            </div>

            <div className="p-5 rounded-2xl bg-[#090f1d] border border-amber-500/30 shadow-xl space-y-2">
              <h3 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" />
                Secondary Risk Check
              </h3>
              <div className="text-sm font-bold text-slate-100">{result.secondary_risk_check.status}</div>
              <p className="text-[11px] text-slate-400 leading-relaxed">{result.secondary_risk_check.risk_assessment}</p>
              <div className="text-[10px] text-slate-500 pt-2 border-t border-slate-800">
                Screened catalog objects: {result.secondary_risk_check.screened_catalog_objects}
              </div>
            </div>
          </div>

          {/* Trajectory scrub */}
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">Trajectory Comparison</h3>
              <span className="text-[10px] text-slate-500">
                {result.trajectory_comparison.trajectory_points.length} computed points
              </span>
            </div>

            <div className="flex items-center gap-3 text-xs">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="p-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
              <span className="text-[11px] text-cyan-300 font-bold whitespace-nowrap">
                {currentPoint
                  ? `TCA ${currentPoint.time_offset_seconds >= 0 ? '+' : ''}${(currentPoint.time_offset_seconds / 3600).toFixed(1)} h`
                  : 'no points'}
              </span>
              <input
                type="range"
                min={0}
                max={Math.max(0, trajectoryPoints.length - 1)}
                value={pointIndex}
                onChange={(e) => setPointIndex(Number(e.target.value))}
                className="flex-1 accent-cyan-500 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
              />
              <span className="text-[10px] text-slate-400 whitespace-nowrap">
                {trajectoryPoints.length === 0 ? '0/0' : `${pointIndex + 1}/${trajectoryPoints.length}`}
              </span>
            </div>

            {currentPoint && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[11px]">
                <div><span className="text-slate-500 block">Radial Delta</span><span className="text-slate-200">{currentPoint.radial_delta_km.toFixed(3)} km</span></div>
                <div><span className="text-slate-500 block">In-Track Delta</span><span className="text-slate-200">{currentPoint.in_track_delta_km.toFixed(3)} km</span></div>
                <div><span className="text-slate-500 block">Cross-Track Delta</span><span className="text-slate-200">{currentPoint.cross_track_delta_km.toFixed(3)} km</span></div>
                <div><span className="text-slate-500 block">Separation Delta</span><span className="text-emerald-400 font-bold">{currentPoint.separation_delta_km.toFixed(3)} km</span></div>
              </div>
            )}

            <p className="text-[10px] text-slate-500 leading-relaxed">
              {result.executive_engineering_debrief}
            </p>
          </div>

          {/* Candidate table */}
          <div className="p-5 rounded-2xl bg-[#090f1d] border border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Fuel className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                  Candidate Avoidance Strategies & Propellant Comparison
                </h3>
              </div>
              <span className="text-[10px] text-slate-500">Tsiolkovsky equation</span>
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
                    <th className="py-2.5 px-3">CARA Tier</th>
                    <th className="py-2.5 px-3 text-right">Select</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {result.candidates_evaluated.map((cand) => {
                    const isSelected = selectedCandidate.candidate_id === cand.candidate_id;
                    return (
                      <tr
                        key={cand.candidate_id}
                        onClick={() => {
                          setSelectedCandidate(cand);
                          setPointIndex(0);
                        }}
                        className={`hover:bg-slate-900/60 cursor-pointer transition-colors ${
                          isSelected ? 'bg-cyan-950/40 border-l-2 border-cyan-400' : ''
                        }`}
                      >
                        <td className="py-3 px-3 font-bold text-cyan-400">{cand.candidate_id}</td>
                        <td className="py-3 px-3 font-semibold text-slate-200">{cand.name}</td>
                        <td className="py-3 px-3 font-bold text-emerald-400">{cand.delta_v_ms}</td>
                        <td className="py-3 px-3">{cand.fuel_mass_kg} kg</td>
                        <td className="py-3 px-3 font-bold text-cyan-300">{cand.projected_miss_distance_km} km</td>
                        <td className="py-3 px-3 text-purple-400 font-bold">{cand.fuel_efficiency_km_per_kg}</td>
                        <td className="py-3 px-3">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-900 text-slate-300 border border-slate-700">
                            {cand.post_maneuver_cara_tier}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            className={`px-3 py-1 rounded-lg text-[10px] font-bold transition-colors ${
                              isSelected ? 'bg-cyan-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
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

            <div className="flex items-center gap-2 text-[10px] text-slate-500">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-500/60" />
              Computed from the supplied scenario inputs. Review requires a separate HITL approval workflow.
            </div>
          </div>
        </>
      )}
    </div>
  );
};
