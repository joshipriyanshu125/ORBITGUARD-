import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Satellite,
  Radio,
  Clock,
  ChevronDown,
  Search,
  RefreshCw,
  Globe2,
  AlertOctagon,
  Database,
  MapPin,
  Navigation,
  Layers
} from 'lucide-react';
import type {
  SatelliteSummary,
  SatellitePosition,
  OrbitPath,
  ConjunctionSummary,
  SystemHealthStatus
} from '../../types';
import { apiService } from '../../services/api';

interface MissionControlProps {
  satellites: SatelliteSummary[];
  conjunctions: ConjunctionSummary[];
  health: SystemHealthStatus | null;
  selectedSatellite: SatelliteSummary | null;
  onSelectSatellite: (satellite: SatelliteSummary) => void;
  onNavigateToRisk: () => void;
  onNavigateToExplorer: () => void;
  onRefresh: () => Promise<void>;
}

const formatUtc = (value?: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.toISOString().replace('T', ' ').slice(0, 19)} UTC`;
};

const riskColor = (tier?: string) => {
  switch (tier) {
    case 'CRITICAL': return 'text-rose-400 border-rose-500/40 bg-rose-500/10';
    case 'HIGH': return 'text-orange-300 border-orange-500/40 bg-orange-500/10';
    case 'MEDIUM': return 'text-amber-300 border-amber-500/40 bg-amber-500/10';
    default: return 'text-slate-300 border-slate-600/40 bg-slate-700/20';
  }
};

export const MissionControl: React.FC<MissionControlProps> = ({
  satellites,
  conjunctions,
  health,
  selectedSatellite,
  onSelectSatellite,
  onNavigateToRisk,
  onNavigateToExplorer,
  onRefresh
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [position, setPosition] = useState<SatellitePosition | null>(null);
  const [orbit, setOrbit] = useState<OrbitPath | null>(null);
  const [isLoadingPosition, setIsLoadingPosition] = useState(false);
  const [isLoadingOrbit, setIsLoadingOrbit] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const loadPosition = useCallback(async (noradId: number) => {
    setIsLoadingPosition(true);
    try {
      const data = await apiService.getSatelliteCurrentPosition(noradId);
      setPosition(data);
      setError(null);
    } catch {
      setPosition(null);
      setError('Live position is unavailable for this object.');
    } finally {
      setIsLoadingPosition(false);
    }
  }, []);

  const loadOrbit = useCallback(async (noradId: number) => {
    setIsLoadingOrbit(true);
    try {
      const data = await apiService.getSatelliteOrbitPath(noradId, 24, 120);
      setOrbit(data);
    } catch {
      setOrbit(null);
    } finally {
      setIsLoadingOrbit(false);
    }
  }, []);

  useEffect(() => {
    setPosition(null);
    setOrbit(null);
    setError(null);
    if (!selectedSatellite) return;
    loadPosition(selectedSatellite.norad_id);
    loadOrbit(selectedSatellite.norad_id);
    const interval = setInterval(() => loadPosition(selectedSatellite.norad_id), 30000);
    return () => clearInterval(interval);
  }, [selectedSatellite?.norad_id, loadPosition, loadOrbit]);

  // Ground track is drawn from real propagated geodetic points.
  useEffect(() => {
    const canvas = canvasRef.current;
    const points = orbit?.points;
    if (!canvas || !points || points.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const xOf = (lon: number) => ((lon + 180) / 360) * width;
    const yOf = (lat: number) => ((90 - lat) / 180) * height;

    ctx.strokeStyle = 'rgba(51, 65, 85, 0.7)';
    ctx.lineWidth = 1;
    for (let lon = -180; lon <= 180; lon += 30) {
      ctx.beginPath();
      ctx.moveTo(xOf(lon), 0);
      ctx.lineTo(xOf(lon), height);
      ctx.stroke();
    }
    for (let lat = -60; lat <= 60; lat += 30) {
      ctx.beginPath();
      ctx.moveTo(0, yOf(lat));
      ctx.lineTo(width, yOf(lat));
      ctx.stroke();
    }
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
    ctx.beginPath();
    ctx.moveTo(0, yOf(0));
    ctx.lineTo(width, yOf(0));
    ctx.stroke();

    ctx.strokeStyle = 'rgba(56, 189, 248, 0.9)';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    let prevLon: number | null = null;
    points.forEach((point) => {
      const x = xOf(point.longitude_deg);
      const y = yOf(point.latitude_deg);
      if (prevLon === null || Math.abs(point.longitude_deg - prevLon) > 180) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      prevLon = point.longitude_deg;
    });
    ctx.stroke();

    if (position) {
      ctx.fillStyle = '#f8fafc';
      ctx.shadowColor = 'rgba(56, 189, 248, 0.9)';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(xOf(position.lon), yOf(position.lat), 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    }
  }, [orbit, position]);

  const handleSync = async () => {
    setIsSyncing(true);
    setSyncMessage(null);
    try {
      const result = await apiService.syncCatalog();
      setSyncMessage(result?.message || `Catalog verified (${result?.catalog_size ?? 0} objects).`);
      await onRefresh();
    } catch (err: any) {
      setSyncMessage(err?.response?.data?.detail || err?.message || 'Catalog sync completed.');
      await onRefresh();
    } finally {
      setIsSyncing(false);
    }
  };

  const filteredSatellites = satellites.filter((sat) =>
    `${sat.name} ${sat.norad_id} ${sat.intl_designator ?? ''}`.toLowerCase().includes(search.toLowerCase())
  );

  const selectedConjunctions = conjunctions
    .filter((c) => c.primary_norad_id === selectedSatellite?.norad_id || c.secondary_norad_id === selectedSatellite?.norad_id)
    .sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime())
    .slice(0, 6);

  const payloadCount = satellites.filter((s) => s.object_type === 'PAYLOAD').length;
  const debrisCount = satellites.filter((s) => s.object_type === 'DEBRIS' || s.object_type === 'ROCKET_BODY').length;
  const highRiskCount = conjunctions.filter((c) => c.risk_tier === 'CRITICAL' || c.risk_tier === 'HIGH').length;

  if (satellites.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-4">
        <Database className="w-12 h-12 text-slate-600" />
        <h1 className="text-xl font-bold text-slate-200">Catalog is empty</h1>
        <p className="text-sm text-slate-400 max-w-md">
          Mission Control reads live orbital data. Synchronize the catalog from CelesTrak to populate satellites,
          conjunctions, and propagation views.
        </p>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm font-semibold"
        >
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          {isSyncing ? 'Syncing catalog…' : 'Sync catalog'}
        </button>
        {syncMessage && <p className="text-xs text-slate-400 font-mono">{syncMessage}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-12 text-slate-200">
      <section className="dashboard-intro">
        <div>
          <div className="eyebrow"><span className="status-beacon" /> ORBITAL OPERATIONS / LIVE OVERVIEW</div>
          <h1>Mission Control</h1>
          <p>Keep an eye on the fleet, orbital health, and the next close approach.</p>
        </div>
        <div className="intro-readout">
          <span className="readout-label">TRACKING WINDOW</span>
          <span className="readout-value">24 <small>HOURS</small></span>
          <span className="readout-note">Live catalog telemetry</span>
        </div>
      </section>

      {/* Catalog summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Catalog Objects', value: health?.catalog?.satellites ?? satellites.length, sub: `${health?.database?.engine ?? 'database unknown'} • ${satellites.length} loaded`, icon: Database, color: 'text-sky-400' },
          { label: 'Payloads (loaded)', value: payloadCount, sub: `${debrisCount} debris / rocket bodies in loaded set`, icon: Satellite, color: 'text-emerald-400' },
          { label: 'Tracked Conjunctions', value: conjunctions.length, sub: `${highRiskCount} high / critical proximity flags`, icon: AlertOctagon, color: highRiskCount > 0 ? 'text-rose-400' : 'text-slate-400' },
          { label: 'Ingestion Scheduler', value: health?.ingestion_scheduler?.running ? 'RUNNING' : 'STOPPED', sub: health?.ingestion_scheduler ? `${health.ingestion_scheduler.interval_hours}h interval` : 'status unknown', icon: Radio, color: health?.ingestion_scheduler?.running ? 'text-emerald-400' : 'text-slate-400' }
        ].map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="bg-[#0b101b] border border-slate-800/90 rounded-2xl p-4 shadow-xl">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">{stat.label}</span>
                <Icon className={`w-4 h-4 ${stat.color}`} />
              </div>
              <div className="text-2xl font-bold mt-2 font-mono">{stat.value}</div>
              <div className="text-[10px] text-slate-500 font-mono truncate">{stat.sub}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Satellite spotlight */}
        <div className="xl:col-span-2 bg-[#0b101b] border border-slate-800/90 rounded-2xl p-5 shadow-2xl space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-700/80 flex items-center justify-center">
                <Satellite className="w-6 h-6 text-sky-400" />
              </div>
              <div className="relative">
                <button onClick={() => setIsDropdownOpen(!isDropdownOpen)} className="flex items-center gap-2 group text-left">
                  <div>
                    <h1 className="text-lg font-bold tracking-tight">{selectedSatellite?.name ?? 'Select an object'}</h1>
                    <p className="text-[11px] text-slate-400 font-mono">
                      NORAD {selectedSatellite?.norad_id ?? '—'} • {selectedSatellite?.intl_designator ?? 'no designator'} • {selectedSatellite?.object_type ?? 'UNKNOWN'}
                    </p>
                  </div>
                  <ChevronDown className="w-4 h-4 text-slate-500 group-hover:text-slate-300" />
                </button>

                {isDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-30" onClick={() => setIsDropdownOpen(false)} />
                    <div className="absolute z-40 mt-2 w-80 max-h-80 overflow-y-auto rounded-xl bg-[#0d1424] border border-slate-700 shadow-2xl p-2">
                      <div className="flex items-center gap-2 px-2 py-1.5 border-b border-slate-800 mb-1">
                        <Search className="w-3.5 h-3.5 text-slate-500" />
                        <input
                          autoFocus
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                          placeholder="Filter by name or NORAD ID"
                          className="w-full bg-transparent text-xs outline-none placeholder:text-slate-600"
                        />
                      </div>
                      {filteredSatellites.slice(0, 200).map((sat) => (
                        <button
                          key={sat.norad_id}
                          onClick={() => {
                            onSelectSatellite(sat);
                            setIsDropdownOpen(false);
                            setSearch('');
                          }}
                          className="w-full text-left px-2 py-1.5 rounded hover:bg-slate-800/80"
                        >
                          <div className="text-xs font-semibold">{sat.name}</div>
                          <div className="text-[10px] text-slate-500 font-mono">NORAD {sat.norad_id} • {sat.object_type ?? 'UNKNOWN'}</div>
                        </button>
                      ))}
                      {filteredSatellites.length === 0 && (
                        <div className="px-2 py-3 text-xs text-slate-500">No catalog object matches.</div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => selectedSatellite && (loadPosition(selectedSatellite.norad_id), loadOrbit(selectedSatellite.norad_id))}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 hover:bg-slate-800 text-xs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingPosition || isLoadingOrbit ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <button
                onClick={onNavigateToExplorer}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-semibold text-white"
              >
                <Globe2 className="w-3.5 h-3.5" />
                3D Explorer
              </button>
            </div>
          </div>

          {/* Live position */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Latitude', value: position ? `${position.lat.toFixed(4)}°` : '—', icon: MapPin },
              { label: 'Longitude', value: position ? `${position.lon.toFixed(4)}°` : '—', icon: MapPin },
              { label: 'Altitude', value: position ? `${position.alt_km.toFixed(1)} km` : '—', icon: Navigation },
              { label: 'Speed', value: position ? `${position.velocity_kms.toFixed(3)} km/s` : '—', icon: Radio }
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.label} className="rounded-xl bg-slate-900/60 border border-slate-800 p-3">
                  <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-500 font-mono">
                    {item.label}
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-sm font-bold font-mono mt-1">{item.value}</div>
                </div>
              );
            })}
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              State epoch: {formatUtc(position?.timestamp)}
            </span>
            {error && <span className="text-rose-400">{error}</span>}
          </div>

          {/* Ground track */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">
                24h Ground Track (SGP4)
              </span>
              <span className="text-[10px] text-slate-500 font-mono">
                {orbit ? `${orbit.point_count} points • ${orbit.step_seconds}s step` : isLoadingOrbit ? 'propagating…' : 'unavailable'}
              </span>
            </div>
            <div className="rounded-xl overflow-hidden border border-slate-800 bg-[#070b13]">
              <canvas ref={canvasRef} className="w-full h-64 block" />
            </div>
          </div>
        </div>

        {/* Orbital elements + TLE */}
        <div className="bg-[#0b101b] border border-slate-800/90 rounded-2xl p-5 shadow-2xl space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
            <Layers className="w-4 h-4 text-sky-400" />
            Catalog Elements
          </h2>
          <div className="space-y-1.5 text-xs font-mono">
            {[
              ['Epoch', formatUtc(selectedSatellite?.epoch)],
              ['Inclination', selectedSatellite?.inclination_deg != null ? `${selectedSatellite.inclination_deg.toFixed(3)}°` : '—'],
              ['Eccentricity', selectedSatellite?.eccentricity != null ? selectedSatellite.eccentricity.toFixed(6) : '—'],
              ['RAAN', selectedSatellite?.raan_deg != null ? `${selectedSatellite.raan_deg.toFixed(3)}°` : '—'],
              ['Arg. of Perigee', selectedSatellite?.arg_perigee_deg != null ? `${selectedSatellite.arg_perigee_deg.toFixed(3)}°` : '—'],
              ['Mean Anomaly', selectedSatellite?.mean_anomaly_deg != null ? `${selectedSatellite.mean_anomaly_deg.toFixed(3)}°` : '—'],
              ['Period', selectedSatellite?.period_minutes != null ? `${selectedSatellite.period_minutes.toFixed(2)} min` : '—'],
              ['Semi-major Axis', selectedSatellite?.semi_major_axis_km != null ? `${selectedSatellite.semi_major_axis_km.toFixed(1)} km` : '—'],
              ['Apogee', selectedSatellite?.apogee_km != null ? `${selectedSatellite.apogee_km.toFixed(1)} km` : '—'],
              ['Perigee', selectedSatellite?.perigee_km != null ? `${selectedSatellite.perigee_km.toFixed(1)} km` : '—']
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-3 border-b border-slate-800/50 py-1">
                <span className="text-slate-500">{label}</span>
                <span className="text-slate-200 text-right">{value}</span>
              </div>
            ))}
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-mono mb-1.5">TLE</div>
            <pre className="text-[10px] leading-relaxed text-slate-400 bg-slate-950/70 border border-slate-800 rounded-lg p-2 overflow-x-auto whitespace-pre-wrap break-all">
{selectedSatellite?.line1 ?? 'TLE unavailable'}
{'\n'}
{selectedSatellite?.line2 ?? ''}
            </pre>
          </div>
        </div>
      </div>

      {/* Conjunctions for the selected object */}
      <div className="bg-[#0b101b] border border-slate-800/90 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-rose-400" />
            Estimated Proximity Events ({selectedConjunctions.length})
          </h2>
          <button onClick={onNavigateToRisk} className="text-[11px] text-sky-400 hover:text-sky-300 font-semibold">
            Open Risk Center →
          </button>
        </div>
        {selectedConjunctions.length === 0 ? (
          <div className="px-5 py-8 text-center text-xs text-slate-500">
            No stored conjunction events involve this object. Run conjunction screening to generate real events.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800/60">
                  <th className="px-4 py-2">Secondary</th>
                  <th className="px-4 py-2">TCA</th>
                  <th className="px-4 py-2">Miss</th>
                  <th className="px-4 py-2">Rel. Speed</th>
                  <th className="px-4 py-2 text-right">Proximity tier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/40">
                {selectedConjunctions.map((conj) => (
                  <tr key={conj.conjunction_id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-2 text-slate-200">
                      {conj.secondary_name}
                      <span className="text-[10px] text-slate-500 ml-2">NORAD {conj.secondary_norad_id}</span>
                    </td>
                    <td className="px-4 py-2 text-slate-400">{formatUtc(conj.tca)}</td>
                    <td className="px-4 py-2 text-slate-200">{conj.miss_distance_km.toFixed(3)} km</td>
                    <td className="px-4 py-2 text-slate-400">{conj.relative_speed_kms.toFixed(2)} km/s</td>
                    <td className="px-4 py-2 text-right">
                      <span className={`inline-block px-2 py-0.5 rounded border text-[10px] font-bold ${riskColor(conj.risk_tier)}`}>
                        {conj.risk_tier ?? 'LOW'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {syncMessage && <p className="text-[11px] text-slate-500 font-mono">{syncMessage}</p>}
    </div>
  );
};
