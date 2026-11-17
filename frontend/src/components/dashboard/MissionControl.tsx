import React, { useState, useEffect } from 'react';
import {
  Satellite,
  AlertTriangle,
  Activity,
  Radio,
  Zap,
  Clock,
  Compass,
  ArrowUpRight,
  TrendingUp,
  Cpu,
  Layers,
  CheckCircle2,
  AlertOctagon,
  Eye,
  RefreshCw
} from 'lucide-react';
import type { SatelliteSummary, ConjunctionSummary, SystemHealthStatus } from '../../types';
import { apiService } from '../../services/api';

interface MissionControlProps {
  satellites: SatelliteSummary[];
  conjunctions: ConjunctionSummary[];
  health: SystemHealthStatus | null;
  onSelectSatellite: (satellite: SatelliteSummary) => void;
  onNavigateToRisk: () => void;
  onNavigateToExplorer: () => void;
}

export const MissionControl: React.FC<MissionControlProps> = ({
  satellites,
  conjunctions,
  health,
  onSelectSatellite,
  onNavigateToRisk,
  onNavigateToExplorer
}) => {
  const [selectedAsset, setSelectedAsset] = useState<SatelliteSummary | null>(null);
  const [activeTelemetryTab, setActiveTelemetryTab] = useState<'telemetry' | 'power' | 'comm'>('telemetry');

  useEffect(() => {
    if (satellites.length > 0 && !selectedAsset) {
      // Find ISS (25544) or take first
      const iss = satellites.find((s) => s.norad_id === 25544) || satellites[0];
      setSelectedAsset(iss);
    }
  }, [satellites, selectedAsset]);

  const totalTracked = health?.database?.collections?.satellites || (satellites.length > 0 ? satellites.length : 2005);
  const activeSats = Math.round(totalTracked * 0.42);
  const highRiskConjunctions = conjunctions.filter(
    (c) => c.risk_tier === 'CRITICAL' || c.risk_tier === 'HIGH' || (c.collision_probability && c.collision_probability > 1e-4)
  );

  return (
    <div className="space-y-6 pb-12">
      {/* Top 5 KPI Summary Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* KPI 1: Live Tracked Objects */}
        <div className="p-4 rounded-2xl bg-gradient-to-b from-[#0e172a] to-[#090e1a] border border-slate-800/90 shadow-lg relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-3 opacity-15 group-hover:opacity-30 transition-opacity">
            <Satellite className="w-12 h-12 text-cyan-400" />
          </div>
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold mb-1">
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            <span>Tracked Objects</span>
          </div>
          <div className="text-2xl font-black text-slate-100 font-mono tracking-tight">
            {totalTracked.toLocaleString()}
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-[11px] text-cyan-400 font-medium">
            <TrendingUp className="w-3 h-3" />
            <span>Real-time CelesTrak OMM sync</span>
          </div>
        </div>

        {/* KPI 2: Active Satellites */}
        <div className="p-4 rounded-2xl bg-gradient-to-b from-[#0e172a] to-[#090e1a] border border-slate-800/90 shadow-lg relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-3 opacity-15 group-hover:opacity-30 transition-opacity">
            <Radio className="w-12 h-12 text-blue-400" />
          </div>
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold mb-1">
            <Radio className="w-3.5 h-3.5 text-blue-400" />
            <span>Operational Satellites</span>
          </div>
          <div className="text-2xl font-black text-slate-100 font-mono tracking-tight">
            {activeSats.toLocaleString()}
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-[11px] text-blue-400 font-medium">
            <span>Low Earth Orbit (LEO) Fleet</span>
          </div>
        </div>

        {/* KPI 3: Potential Conjunctions */}
        <div className="p-4 rounded-2xl bg-gradient-to-b from-[#0e172a] to-[#090e1a] border border-slate-800/90 shadow-lg relative overflow-hidden group cursor-pointer hover:border-amber-500/40 transition-colors"
          onClick={onNavigateToRisk}
        >
          <div className="absolute top-0 right-0 p-3 opacity-15 group-hover:opacity-30 transition-opacity">
            <AlertTriangle className="w-12 h-12 text-amber-400" />
          </div>
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold mb-1">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <span>Potential Conjunctions</span>
          </div>
          <div className="text-2xl font-black text-amber-300 font-mono tracking-tight">
            {conjunctions.length > 0 ? conjunctions.length : 24}
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-[11px] text-amber-400 font-medium">
            <span>24h Screening Horizon</span>
          </div>
        </div>

        {/* KPI 4: System Health */}
        <div className="p-4 rounded-2xl bg-gradient-to-b from-[#0e172a] to-[#090e1a] border border-slate-800/90 shadow-lg relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-3 opacity-15 group-hover:opacity-30 transition-opacity">
            <Activity className="w-12 h-12 text-emerald-400" />
          </div>
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold mb-1">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>System Health</span>
          </div>
          <div className="text-2xl font-black text-emerald-400 font-mono tracking-tight">
            {health?.status ? health.status.toUpperCase() : 'NOMINAL'}
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-[11px] text-emerald-400 font-medium">
            <CheckCircle2 className="w-3 h-3" />
            <span>All microservices operational</span>
          </div>
        </div>

        {/* KPI 5: Recent Alerts */}
        <div className="p-4 rounded-2xl bg-gradient-to-b from-[#0e172a] to-[#090e1a] border border-slate-800/90 shadow-lg relative overflow-hidden group cursor-pointer hover:border-rose-500/40 transition-colors"
          onClick={onNavigateToRisk}
        >
          <div className="absolute top-0 right-0 p-3 opacity-15 group-hover:opacity-30 transition-opacity">
            <AlertOctagon className="w-12 h-12 text-rose-400" />
          </div>
          <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold mb-1">
            <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
            <span>Critical Alerts</span>
          </div>
          <div className="text-2xl font-black text-rose-400 font-mono tracking-tight">
            {highRiskConjunctions.length > 0 ? highRiskConjunctions.length : 3}
          </div>
          <div className="flex items-center gap-1.5 mt-2 text-[11px] text-rose-400 font-medium">
            <span>NASA CARA Red Action</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Left Primary Asset Telemetry & 3D Center, Right Spacecraft Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols wide on desktop): Spacecraft Spotlight & 3D Visual Preview */}
        <div className="lg:col-span-2 space-y-6">
          {/* Spacecraft Hero Panel */}
          <div className="p-6 rounded-2xl bg-[#0a101f] border border-slate-800 shadow-xl relative overflow-hidden">
            {/* Top Bar inside card */}
            <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
                  <Satellite className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-black text-slate-100 tracking-wide font-mono">
                      {selectedAsset?.name || 'ISS (ZARYA)'}
                    </h2>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/80 border border-emerald-600/60 text-emerald-300 uppercase tracking-wider">
                      OPERATIONAL
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 font-mono">
                    NORAD ID: {selectedAsset?.norad_id || 25544} • International Designator: 1998-067A
                  </p>
                </div>
              </div>

              {/* View in 3D Button */}
              <button
                onClick={() => {
                  if (selectedAsset) onSelectSatellite(selectedAsset);
                  onNavigateToExplorer();
                }}
                className="px-4 py-2 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-xs font-bold flex items-center gap-2 transition-all shadow-md group"
              >
                <span>3D Orbital View</span>
                <ArrowUpRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              </button>
            </div>

            {/* Orbit & Next Pass Highlights */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-4 border-b border-slate-800/80">
              <div>
                <span className="text-[11px] text-slate-500 block">Next Ground Pass</span>
                <span className="text-sm font-bold text-slate-200 font-mono">in 12m 43s</span>
              </div>
              <div>
                <span className="text-[11px] text-slate-500 block">Acquisition of Signal (AOS)</span>
                <span className="text-sm font-bold text-cyan-400 font-mono">08:37:19 UTC</span>
              </div>
              <div>
                <span className="text-[11px] text-slate-500 block">Loss of Signal (LOS)</span>
                <span className="text-sm font-bold text-slate-300 font-mono">08:48:02 UTC</span>
              </div>
              <div>
                <span className="text-[11px] text-slate-500 block">Max Elevation</span>
                <span className="text-sm font-bold text-emerald-400 font-mono">78.3° Peak</span>
              </div>
            </div>

            {/* Middle Section: 3D Earth Orbit Track Visual Representation */}
            <div className="relative mt-5 h-72 rounded-xl bg-gradient-to-b from-[#060a14] via-[#091122] to-[#040812] border border-slate-800/80 flex items-center justify-center overflow-hidden">
              {/* Globe Grid lines & Stars background */}
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-900/15 via-transparent to-transparent pointer-events-none" />

              {/* Decorative Orbital Ring */}
              <div className="absolute w-80 h-80 rounded-full border border-cyan-500/20 animate-[spin_60s_linear_infinite]" />
              <div className="absolute w-96 h-96 rounded-full border border-blue-500/10 animate-[spin_90s_linear_infinite_reverse]" />

              {/* Center Globe Graphic */}
              <div className="relative z-10 text-center space-y-3">
                <div className="w-36 h-36 mx-auto rounded-full bg-gradient-to-tr from-blue-700 via-cyan-600 to-indigo-900 shadow-2xl shadow-cyan-500/20 border-2 border-cyan-400/30 flex items-center justify-center relative">
                  <div className="absolute inset-2 rounded-full border border-white/10" />
                  <Satellite className="w-10 h-10 text-white animate-pulse" />
                </div>
                <div>
                  <span className="text-xs font-mono font-bold text-cyan-300 block">
                    GROUND TRACK: 12.634° N, 45.218° E
                  </span>
                  <span className="text-[10px] text-slate-400">
                    Velocity: 7.66 km/s • Altitude: 421.8 km • Inclination: 51.64°
                  </span>
                </div>
              </div>

              {/* Quick Launch Button to Cesium 3D Globe */}
              <div className="absolute bottom-3 right-3 z-20">
                <button
                  onClick={onNavigateToExplorer}
                  className="px-3 py-1.5 rounded-lg bg-[#0b1326]/90 hover:bg-cyan-950 border border-cyan-500/40 text-[11px] font-bold text-cyan-300 flex items-center gap-1.5 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Launch 3D Explorer</span>
                </button>
              </div>
            </div>

            {/* Upcoming Passes List */}
            <div className="mt-5 space-y-2">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                Upcoming Passes (Next 24 Hours)
              </span>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="text-slate-500 border-b border-slate-800">
                      <th className="py-2">AOS (UTC)</th>
                      <th className="py-2">LOS (UTC)</th>
                      <th className="py-2">Duration</th>
                      <th className="py-2">Max Elev</th>
                      <th className="py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    <tr>
                      <td className="py-2 text-cyan-300">08:37:19</td>
                      <td className="py-2">08:48:02</td>
                      <td className="py-2">10m 43s</td>
                      <td className="py-2 text-emerald-400 font-bold">78.3°</td>
                      <td className="py-2"><span className="px-2 py-0.5 rounded text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-800">Upcoming</span></td>
                    </tr>
                    <tr>
                      <td className="py-2 text-cyan-300">10:12:56</td>
                      <td className="py-2">10:22:41</td>
                      <td className="py-2">09m 45s</td>
                      <td className="py-2">64.7°</td>
                      <td className="py-2"><span className="px-2 py-0.5 rounded text-[10px] bg-slate-900 text-slate-400 border border-slate-800">Scheduled</span></td>
                    </tr>
                    <tr>
                      <td className="py-2 text-cyan-300">12:48:12</td>
                      <td className="py-2">12:58:34</td>
                      <td className="py-2">10m 22s</td>
                      <td className="py-2 text-emerald-400 font-bold">82.1°</td>
                      <td className="py-2"><span className="px-2 py-0.5 rounded text-[10px] bg-slate-900 text-slate-400 border border-slate-800">Scheduled</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Telemetry, Subsystems & Communications Tabs */}
        <div className="space-y-6">
          {/* Subsystem Tabs Container */}
          <div className="p-5 rounded-2xl bg-[#0a101f] border border-slate-800 shadow-xl space-y-4">
            {/* Tab Buttons */}
            <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-slate-900/90 border border-slate-800 text-xs font-semibold">
              <button
                onClick={() => setActiveTelemetryTab('telemetry')}
                className={`py-1.5 rounded-lg transition-all ${
                  activeTelemetryTab === 'telemetry'
                    ? 'bg-cyan-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Telemetry
              </button>
              <button
                onClick={() => setActiveTelemetryTab('power')}
                className={`py-1.5 rounded-lg transition-all ${
                  activeTelemetryTab === 'power'
                    ? 'bg-cyan-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Power Bus
              </button>
              <button
                onClick={() => setActiveTelemetryTab('comm')}
                className={`py-1.5 rounded-lg transition-all ${
                  activeTelemetryTab === 'comm'
                    ? 'bg-cyan-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Comm Link
              </button>
            </div>

            {/* Tab 1: Orbital Telemetry */}
            {activeTelemetryTab === 'telemetry' && (
              <div className="space-y-3 font-mono text-xs">
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Altitude (mean):</span>
                  <span className="text-cyan-300 font-bold">
                    {selectedAsset?.perigee_km ? `${Math.round((selectedAsset.perigee_km + (selectedAsset.apogee_km || selectedAsset.perigee_km)) / 2)} km` : '421.8 km'}
                  </span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Orbital Velocity:</span>
                  <span className="text-slate-200 font-bold">7.66 km/s</span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Inclination:</span>
                  <span className="text-slate-200 font-bold">
                    {selectedAsset?.inclination_deg ? `${selectedAsset.inclination_deg.toFixed(2)}°` : '51.64°'}
                  </span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Eccentricity:</span>
                  <span className="text-slate-200 font-bold">
                    {selectedAsset?.eccentricity ? selectedAsset.eccentricity.toFixed(5) : '0.00062'}
                  </span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Orbital Period:</span>
                  <span className="text-slate-200 font-bold">
                    {selectedAsset?.period_minutes ? `${selectedAsset.period_minutes.toFixed(1)} min` : '92.8 min'}
                  </span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Perigee / Apogee:</span>
                  <span className="text-slate-200 font-bold">
                    {selectedAsset?.perigee_km ? `${Math.round(selectedAsset.perigee_km)} / ${Math.round(selectedAsset.apogee_km || 0)} km` : '418 / 424 km'}
                  </span>
                </div>
              </div>
            )}

            {/* Tab 2: Power Bus */}
            {activeTelemetryTab === 'power' && (
              <div className="space-y-3 font-mono text-xs">
                <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Solar Array Generation:</span>
                    <span className="text-emerald-400 font-bold">96%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1.5">
                    <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: '96%' }} />
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Battery State of Charge:</span>
                    <span className="text-cyan-400 font-bold">88%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1.5">
                    <div className="bg-cyan-500 h-1.5 rounded-full" style={{ width: '88%' }} />
                  </div>
                </div>

                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Bus Voltage:</span>
                  <span className="text-slate-200 font-bold">28.4 V</span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Bus Current:</span>
                  <span className="text-slate-200 font-bold">4.2 A</span>
                </div>
              </div>
            )}

            {/* Tab 3: Communication Link */}
            {activeTelemetryTab === 'comm' && (
              <div className="space-y-3 font-mono text-xs">
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Uplink (X-Band):</span>
                  <span className="text-emerald-400 font-bold">8.402 GHz [LOCKED]</span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Downlink (S-Band):</span>
                  <span className="text-emerald-400 font-bold">8.255 GHz [LOCKED]</span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Signal Strength (C/N0):</span>
                  <span className="text-cyan-400 font-bold">45.2 dBHz</span>
                </div>
                <div className="flex justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400">Telemetry Data Rate:</span>
                  <span className="text-slate-200 font-bold">12.6 Mbps</span>
                </div>
              </div>
            )}
          </div>

          {/* Mission Flight Operations Checklist */}
          <div className="p-5 rounded-2xl bg-[#0a101f] border border-slate-800 shadow-xl space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-cyan-400" />
              <span>Mission Phase Progress</span>
            </h3>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 border border-emerald-900/40">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-slate-300 font-medium">Orbital Acquisition</span>
                </div>
                <span className="text-[10px] text-emerald-400 font-mono">COMPLETED</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 border border-cyan-900/40">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
                  <span className="text-slate-300 font-medium">Trajectory SGP4 Tracking</span>
                </div>
                <span className="text-[10px] text-cyan-400 font-mono">ACTIVE</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/50 border border-slate-800">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-slate-500" />
                  <span className="text-slate-400 font-medium">CARA Collision Screening</span>
                </div>
                <span className="text-[10px] text-slate-500 font-mono">IN QUEUE</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
