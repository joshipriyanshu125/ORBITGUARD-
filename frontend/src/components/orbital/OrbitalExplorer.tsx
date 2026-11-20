import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import {
  Search,
  RotateCcw,
  Play,
  Pause,
  Crosshair,
  Satellite as SatelliteIcon,
  X,
  Database
} from 'lucide-react';
import type { SatelliteSummary } from '../../types';
import { apiService } from '../../services/api';

interface OrbitalExplorerProps {
  satellites: SatelliteSummary[];
  selectedSatellite: SatelliteSummary | null;
  onSelectSatellite: (sat: SatelliteSummary | null) => void;
}

interface LivePosition {
  norad_id: number;
  name: string;
  object_type: string;
  lat: number;
  lon: number;
  alt_km: number;
}

export const OrbitalExplorer: React.FC<OrbitalExplorerProps> = ({
  satellites,
  selectedSatellite,
  onSelectSatellite
}) => {
  const cesiumContainerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const orbitEntityRef = useRef<Cesium.Entity | null>(null);
  const satelliteEntitiesRef = useRef<Map<number, Cesium.Entity>>(new Map());
  const satellitesRef = useRef<SatelliteSummary[]>(satellites);

  useEffect(() => {
    satellitesRef.current = satellites;
  }, [satellites]);

  const [searchQuery, setSearchQuery] = useState('');
  const [isRotating, setIsRotating] = useState(true);
  const [rotationSpeed] = useState(0.04);
  const [showDebris, setShowDebris] = useState(true);
  const [showActiveSats, setShowActiveSats] = useState(true);
  const [showOrbitPaths, setShowOrbitPaths] = useState(true);
  const [altitudeRegime, setAltitudeRegime] = useState<'ALL' | 'LEO' | 'MEO' | 'GEO'>('ALL');
  const [positions, setPositions] = useState<Map<number, LivePosition>>(new Map());
  const [positionsEpoch, setPositionsEpoch] = useState<string | null>(null);
  const [currentPosition, setCurrentPosition] = useState<LivePosition | null>(null);
  const [isLoadingOrbit, setIsLoadingOrbit] = useState(false);
  const [orbitError, setOrbitError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedSatellite && satellites.length > 0) {
      onSelectSatellite(satellites[0]);
    }
  }, [selectedSatellite, satellites, onSelectSatellite]);

  // Initialize the Cesium viewer once.
  useEffect(() => {
    if (!cesiumContainerRef.current) return;

    const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
    if (ionToken) {
      Cesium.Ion.defaultAccessToken = ionToken;
    }

    const viewer = new Cesium.Viewer(cesiumContainerRef.current, {
      animation: false,
      timeline: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      navigationHelpButton: false,
      baseLayerPicker: false,
      skyAtmosphere: new Cesium.SkyAtmosphere()
    });

    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(78.0, 18.0, 24000000.0)
    });

    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((movement: any) => {
      const pickedObject = viewer.scene.pick(movement.position);
      if (
        Cesium.defined(pickedObject) &&
        pickedObject.id &&
        typeof pickedObject.id.id === 'string' &&
        pickedObject.id.id.startsWith('sat-')
      ) {
        const noradId = parseInt(pickedObject.id.id.replace('sat-', ''), 10);
        const sat = satellitesRef.current.find((s) => s.norad_id === noradId);
        if (sat) onSelectSatellite(sat);
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    viewerRef.current = viewer;

    return () => {
      handler.destroy();
      if (!viewer.isDestroyed()) viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // Slow camera rotation control.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    let previousTime = Date.now();
    const rotate = () => {
      if (isRotating && viewer && !viewer.isDestroyed()) {
        const now = Date.now();
        const delta = (now - previousTime) / 1000;
        previousTime = now;
        viewer.scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, delta * rotationSpeed);
      } else {
        previousTime = Date.now();
      }
    };
    viewer.clock.onTick.addEventListener(rotate);
    return () => {
      if (viewer && !viewer.isDestroyed()) viewer.clock.onTick.removeEventListener(rotate);
    };
  }, [isRotating, rotationSpeed]);

  // Live SGP4 positions for the catalog (batch endpoint, refreshed every 60s).
  useEffect(() => {
    if (satellites.length === 0) {
      setPositions(new Map());
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const data = await apiService.getCatalogPositions(satellites.slice(0, 2500).map((s) => s.norad_id));
        if (cancelled) return;
        const map = new Map<number, LivePosition>();
        data.items.forEach((item) => map.set(item.norad_id, item));
        setPositions(map);
        setPositionsEpoch(data.timestamp);
      } catch {
        if (!cancelled) setPositionsEpoch(null);
      }
    };
    load();
    const interval = setInterval(load, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [satellites]);

  // Render catalog points from live propagated states.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    satelliteEntitiesRef.current.forEach((entity) => viewer.entities.remove(entity));
    satelliteEntitiesRef.current.clear();

    const entitiesMap = new Map<number, Cesium.Entity>();
    satellites.forEach((sat) => {
      const live = positions.get(sat.norad_id);
      if (!live) return;

      const isDebris = sat.object_type === 'DEBRIS' || sat.object_type === 'ROCKET_BODY';
      if (isDebris && !showDebris) return;
      if (!isDebris && !showActiveSats) return;

      const alt = live.alt_km;
      if (altitudeRegime === 'LEO' && alt > 2000) return;
      if (altitudeRegime === 'MEO' && (alt < 2000 || alt > 35000)) return;
      if (altitudeRegime === 'GEO' && alt < 35000) return;

      const isSelected = selectedSatellite?.norad_id === sat.norad_id;
      let pointColor = isDebris
        ? Cesium.Color.fromCssColorString('#f87171').withAlpha(0.65)
        : Cesium.Color.fromCssColorString('#22c55e');
      let pixelSize = isDebris ? 2.5 : 3.5;

      if (isSelected) {
        pointColor = Cesium.Color.fromCssColorString('#fbbf24');
        pixelSize = 8.0;
      }

      const entity = viewer.entities.add({
        id: `sat-${sat.norad_id}`,
        name: sat.name,
        position: Cesium.Cartesian3.fromDegrees(live.lon, live.lat, live.alt_km * 1000),
        point: {
          pixelSize,
          color: pointColor,
          outlineColor: isSelected ? Cesium.Color.WHITE : Cesium.Color.BLACK,
          outlineWidth: isSelected ? 2 : 1,
          scaleByDistance: new Cesium.NearFarScalar(1.5e6, 2.0, 4.5e7, 0.5)
        }
      });
      entitiesMap.set(sat.norad_id, entity);
    });

    satelliteEntitiesRef.current = entitiesMap;
  }, [satellites, positions, showDebris, showActiveSats, altitudeRegime, selectedSatellite]);

  // Real SGP4 orbit path for the selected object.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    if (orbitEntityRef.current) {
      viewer.entities.remove(orbitEntityRef.current);
      orbitEntityRef.current = null;
    }
    setOrbitError(null);
    setCurrentPosition(null);
    if (!selectedSatellite) return;

    const live = positions.get(selectedSatellite.norad_id) ?? null;
    setCurrentPosition(live);
    if (!showOrbitPaths) return;

    let cancelled = false;
    setIsLoadingOrbit(true);
    apiService
      .getSatelliteOrbitPath(selectedSatellite.norad_id, 24, 120)
      .then((data) => {
        if (cancelled || !viewer || viewer.isDestroyed() || !data.points?.length) return;
        const points = data.points
          .filter((pt: any) => pt.latitude_deg !== undefined && pt.longitude_deg !== undefined)
          .map((pt: any) => Cesium.Cartesian3.fromDegrees(pt.longitude_deg, pt.latitude_deg, Math.max(pt.altitude_km * 1000, 150000)));
        if (points.length > 2) {
          orbitEntityRef.current = viewer.entities.add({
            name: `${selectedSatellite.name} SGP4 trajectory`,
            polyline: {
              positions: points,
              width: 2.5,
              material: new Cesium.PolylineGlowMaterialProperty({
                glowPower: 0.15,
                color: Cesium.Color.fromCssColorString('#ef4444')
              })
            }
          });
        }
      })
      .catch(() => {
        if (!cancelled) setOrbitError('SGP4 orbit propagation is unavailable for this object.');
      })
      .finally(() => {
        if (!cancelled) setIsLoadingOrbit(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedSatellite, showOrbitPaths, positions]);

  const flyToNorad = useCallback(async (noradId: number) => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    let live = positions.get(noradId);
    if (!live) {
      try {
        live = await apiService.getSatelliteCurrentPosition(noradId);
      } catch {
        return;
      }
    }
    if (!live) return;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(live.lon, live.lat, (live.alt_km + 4200) * 1000),
      duration: 1.8
    });
  }, [positions]);

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    return satellites
      .filter((s) => s.name.toLowerCase().includes(q) || s.norad_id.toString().includes(q))
      .slice(0, 8);
  }, [searchQuery, satellites]);

  return (
    <div className="relative w-full h-[calc(100vh-7.5rem)] rounded-2xl overflow-hidden border border-slate-800 bg-[#060a14] shadow-2xl select-none font-sans">
      <div ref={cesiumContainerRef} className="w-full h-full" />

      {satellites.length === 0 && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center text-center space-y-3 bg-[#060a14]">
          <Database className="w-10 h-10 text-slate-600" />
          <h2 className="text-lg font-bold text-slate-200">No catalog objects to display</h2>
          <p className="text-sm text-slate-400 max-w-md">
            Synchronize the catalog on Mission Control to populate the 3D orbital view with live CelesTrak objects.
          </p>
        </div>
      )}

      {/* Controls */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-2 font-mono text-xs">
        <div className="relative w-72">
          <Search className="w-4 h-4 text-sky-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search catalog name or NORAD..."
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-[#091022]/90 backdrop-blur-md border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 shadow-xl"
          />
          {searchResults.length > 0 && (
            <div className="absolute left-0 right-0 mt-1.5 max-h-60 overflow-y-auto rounded-xl bg-[#091022] border border-slate-800 shadow-2xl divide-y divide-slate-800/60 z-30">
              {searchResults.map((sat) => (
                <button
                  key={sat.norad_id}
                  onClick={() => {
                    onSelectSatellite(sat);
                    flyToNorad(sat.norad_id);
                    setSearchQuery('');
                  }}
                  className="w-full px-3 py-2 text-left hover:bg-sky-950/60 flex items-center justify-between text-slate-300 transition-colors"
                >
                  <span className="font-semibold text-sky-300 truncate">{sat.name}</span>
                  <span className="text-[10px] text-slate-500 shrink-0">#{sat.norad_id}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={() => setIsRotating(!isRotating)}
          className={`p-2 rounded-xl backdrop-blur-md border shadow-xl transition-colors ${
            isRotating
              ? 'bg-sky-950/80 border-sky-500/50 text-sky-300'
              : 'bg-[#091022]/90 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          title={isRotating ? 'Pause camera rotation' : 'Resume camera rotation'}
        >
          {isRotating ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
        </button>

        <button
          onClick={() => viewerRef.current?.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(78.0, 18.0, 24000000.0),
            duration: 1.5
          })}
          className="p-2 rounded-xl bg-[#091022]/90 backdrop-blur-md border border-slate-800 text-slate-400 hover:text-sky-300 shadow-xl transition-colors"
          title="Reset global view"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>

        {selectedSatellite && (
          <button
            onClick={() => flyToNorad(selectedSatellite.norad_id)}
            className="px-2.5 py-1.5 rounded-xl bg-[#091022]/90 backdrop-blur-md border border-slate-800 text-sky-400 hover:border-sky-500 flex items-center gap-1.5 shadow-xl transition-colors"
            title="Focus camera on selected object"
          >
            <Crosshair className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-[11px] font-bold">Track Object</span>
          </button>
        )}

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#091022]/90 backdrop-blur-md border border-slate-800 shadow-xl text-[11px]">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={showActiveSats} onChange={(e) => setShowActiveSats(e.target.checked)} className="rounded bg-slate-900 border-slate-700 text-emerald-500 focus:ring-0" />
            <span className="text-emerald-400 font-bold">Payloads</span>
          </label>
          <span className="text-slate-700">|</span>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={showDebris} onChange={(e) => setShowDebris(e.target.checked)} className="rounded bg-slate-900 border-slate-700 text-rose-500 focus:ring-0" />
            <span className="text-rose-400 font-bold">Debris</span>
          </label>
          <span className="text-slate-700">|</span>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={showOrbitPaths} onChange={(e) => setShowOrbitPaths(e.target.checked)} className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0" />
            <span className="text-sky-400 font-bold">Orbit Line</span>
          </label>
        </div>

        <div className="flex items-center bg-[#091022]/90 backdrop-blur-md border border-slate-800 rounded-xl p-0.5 shadow-xl">
          {(['ALL', 'LEO', 'MEO', 'GEO'] as const).map((regime) => (
            <button
              key={regime}
              onClick={() => setAltitudeRegime(regime)}
              className={`px-2 py-1 text-[10px] font-bold rounded-lg transition-colors ${
                altitudeRegime === regime ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {regime}
            </button>
          ))}
        </div>
      </div>

      {/* Selected object inspection card */}
      {selectedSatellite && (
        <div className="absolute top-4 right-4 z-20 w-80 rounded-xl bg-[#091329]/95 backdrop-blur-xl border border-slate-700/80 shadow-2xl overflow-hidden font-mono text-xs">
          <div className="bg-[#172554] border-b border-blue-900/80 px-3.5 py-2.5 flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-400 inline-block shrink-0" />
              <h3 className="font-bold text-sky-200 text-sm tracking-wide truncate">{selectedSatellite.name}</h3>
            </div>
            <button
              onClick={() => onSelectSatellite(null)}
              className="p-1 rounded text-sky-300 hover:text-white hover:bg-blue-800/60 transition-colors"
              title="Close panel"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-3.5 space-y-3">
            <div>
              <div className="text-center font-bold text-sky-400 text-xs py-1 mb-1 border-b border-slate-800">Identifiers</div>
              <div className="space-y-1 text-[11px]">
                <div className="flex justify-between"><span className="text-slate-400">COSPAR:</span><span className="text-slate-200">{selectedSatellite.intl_designator ?? '—'}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">NORAD:</span><span className="text-slate-200 font-bold">{selectedSatellite.norad_id}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Type:</span><span className="text-slate-200">{selectedSatellite.object_type ?? 'UNKNOWN'}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Source:</span><span className="text-slate-200">CelesTrak TLE</span></div>
              </div>
            </div>

            <div>
              <div className="text-center font-bold text-sky-400 text-xs py-1 mb-1 border-b border-slate-800">Orbit Data</div>
              <div className="space-y-1 text-[11px]">
                <div className="flex justify-between"><span className="text-slate-400">Apogee:</span><span className="text-slate-100 font-semibold">{selectedSatellite.apogee_km != null ? `${Math.round(selectedSatellite.apogee_km).toLocaleString()} km` : '—'}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Perigee:</span><span className="text-slate-100 font-semibold">{selectedSatellite.perigee_km != null ? `${Math.round(selectedSatellite.perigee_km).toLocaleString()} km` : '—'}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Inclination:</span><span className="text-sky-300 font-semibold">{selectedSatellite.inclination_deg != null ? `${selectedSatellite.inclination_deg.toFixed(2)}°` : '—'}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Eccentricity:</span><span className="text-slate-200">{selectedSatellite.eccentricity != null ? selectedSatellite.eccentricity.toFixed(5) : '—'}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Period:</span><span className="text-slate-200">{selectedSatellite.period_minutes != null ? `${selectedSatellite.period_minutes.toFixed(1)} min` : '—'}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Semi-Major Axis:</span><span className="text-slate-200">{selectedSatellite.semi_major_axis_km != null ? `${Math.round(selectedSatellite.semi_major_axis_km).toLocaleString()} km` : '—'}</span></div>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-[#060c1c] border border-sky-900/60 space-y-1 text-[10px] text-sky-300">
              <div className="flex justify-between"><span className="text-slate-400">Sub-Sat Lat/Lon:</span><span className="font-bold">{currentPosition ? `${currentPosition.lat.toFixed(2)}°, ${currentPosition.lon.toFixed(2)}°` : '—'}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Altitude:</span><span className="font-bold text-slate-200">{currentPosition ? `${currentPosition.alt_km.toFixed(1)} km` : '—'}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">State Epoch:</span><span className="font-bold text-slate-200">{positionsEpoch ? positionsEpoch.slice(11, 19) + ' UTC' : '—'}</span></div>
            </div>

            {isLoadingOrbit && <div className="text-center py-1 text-sky-400 text-[10px] animate-pulse">SGP4 ephemeris syncing…</div>}
            {orbitError && <div className="text-center py-1 text-rose-400 text-[10px]">{orbitError}</div>}
          </div>
        </div>
      )}

      {/* Attribution / live state */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#091329]/90 backdrop-blur-md border border-slate-800 text-[11px] font-mono text-slate-400 shadow-xl">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span>
          CelesTrak TLE &bull; SGP4 propagation &bull;{' '}
          <span className="text-sky-300 font-bold">
            {positions.size} live states
          </span>
        </span>
      </div>
    </div>
  );
};
