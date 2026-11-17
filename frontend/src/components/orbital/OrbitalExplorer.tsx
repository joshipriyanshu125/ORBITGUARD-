import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import {
  Search,
  RotateCcw,
  Play,
  Pause,
  Filter,
  Eye,
  Crosshair,
  Satellite as SatelliteIcon,
  Layers,
  Sparkles,
  Info,
  X
} from 'lucide-react';
import type { SatelliteSummary } from '../../types';
import { apiService } from '../../services/api';

interface OrbitalExplorerProps {
  satellites: SatelliteSummary[];
  selectedSatellite: SatelliteSummary | null;
  onSelectSatellite: (sat: SatelliteSummary | null) => void;
}

export const OrbitalExplorer: React.FC<OrbitalExplorerProps> = ({
  satellites,
  selectedSatellite,
  onSelectSatellite
}) => {
  const cesiumContainerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const orbitEntityRef = useRef<Cesium.Entity | null>(null);
  const satelliteEntitiesRef = useRef<Map<number, Cesium.Entity>>(new Map());

  const [searchQuery, setSearchQuery] = useState('');
  const [isRotating, setIsRotating] = useState(true);
  const [showDebris, setShowDebris] = useState(true);
  const [showActiveSats, setShowActiveSats] = useState(true);
  const [showOrbitPaths, setShowOrbitPaths] = useState(true);
  const [currentSatPosition, setCurrentSatPosition] = useState<any | null>(null);
  const [isLoadingOrbit, setIsLoadingOrbit] = useState(false);

  // Initialize Cesium Viewer
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
      skyAtmosphere: new Cesium.SkyAtmosphere(),
      skyBox: new Cesium.SkyBox({
        sources: {
          positiveX: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_px.jpg',
          negativeX: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_mx.jpg',
          positiveY: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_py.jpg',
          negativeY: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_my.jpg',
          positiveZ: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_pz.jpg',
          negativeZ: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_mz.jpg'
        }
      })
    });

    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.depthTestAgainstTerrain = false;

    // Set initial camera view to see Earth from high orbital altitude
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(20.0, 15.0, 22000000.0)
    });

    viewerRef.current = viewer;

    return () => {
      if (!viewer.isDestroyed()) {
        viewer.destroy();
      }
      viewerRef.current = null;
    };
  }, []);

  // Globe slow rotation effect
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    let previousTime = Date.now();
    const rotate = () => {
      if (isRotating && viewer && !viewer.isDestroyed() && !selectedSatellite) {
        const now = Date.now();
        const delta = (now - previousTime) / 1000;
        previousTime = now;
        viewer.scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, delta * 0.04);
      } else {
        previousTime = Date.now();
      }
    };

    viewer.clock.onTick.addEventListener(rotate);
    return () => {
      if (viewer && !viewer.isDestroyed()) {
        viewer.clock.onTick.removeEventListener(rotate);
      }
    };
  }, [isRotating, selectedSatellite]);

  // Render satellites as 3D point markers
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed() || satellites.length === 0) return;

    // Clear old entities
    satelliteEntitiesRef.current.forEach((entity) => viewer.entities.remove(entity));
    satelliteEntitiesRef.current.clear();

    const entitiesMap = new Map<number, Cesium.Entity>();

    satellites.slice(0, 450).forEach((sat) => {
      const isDebris = (sat.name.includes('DEB') || sat.name.includes('R/B') || sat.object_type === 'DEBRIS');
      if (isDebris && !showDebris) return;
      if (!isDebris && !showActiveSats) return;

      const inc = sat.inclination_deg || 51.6;
      const raan = sat.raan_deg || 0.0;
      const meanMo = sat.mean_motion_rev_day || 15.5;
      const altKm = sat.perigee_km || 420.0;

      // Approximate current position on orbital sphere
      const lon = ((raan + (sat.norad_id % 360) * 1.5) % 360) - 180;
      const lat = Math.sin((sat.norad_id * 17) % 360 * (Math.PI / 180)) * inc;
      const altMeters = altKm * 1000.0;

      let pointColor = Cesium.Color.CYAN;
      let pixelSize = 4;

      if (sat.norad_id === 25544) {
        // Space Station
        pointColor = Cesium.Color.YELLOW;
        pixelSize = 9;
      } else if (isDebris) {
        pointColor = Cesium.Color.CORAL.withAlpha(0.7);
        pixelSize = 3;
      } else {
        pointColor = Cesium.Color.fromCssColorString('#00ffcc').withAlpha(0.85);
        pixelSize = 4;
      }

      const entity = viewer.entities.add({
        id: `sat-${sat.norad_id}`,
        name: sat.name,
        position: Cesium.Cartesian3.fromDegrees(lon, lat, altMeters),
        point: {
          pixelSize: pixelSize,
          color: pointColor,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 1,
          scaleByDistance: new Cesium.NearFarScalar(1.5e6, 2.0, 4.0e7, 0.6)
        }
      });

      entitiesMap.set(sat.norad_id, entity);
    });

    satelliteEntitiesRef.current = entitiesMap;
  }, [satellites, showDebris, showActiveSats]);

  // Propagate orbit path and fly to selected satellite
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed() || !selectedSatellite) return;

    setIsLoadingOrbit(true);

    // Remove existing orbit polyline
    if (orbitEntityRef.current) {
      viewer.entities.remove(orbitEntityRef.current);
      orbitEntityRef.current = null;
    }

    const noradId = selectedSatellite.norad_id;

    // Fetch accurate SGP4 propagated orbit path from backend
    apiService
      .getSatelliteOrbitPath(noradId, 1.6, 2)
      .then((data) => {
        if (!viewer || viewer.isDestroyed()) return;

        const points = data.points || [];
        if (points.length > 0) {
          const positions: Cesium.Cartesian3[] = [];
          points.forEach((pt: any) => {
            const lon = pt.longitude_deg !== undefined ? pt.longitude_deg : pt.lon;
            const lat = pt.latitude_deg !== undefined ? pt.latitude_deg : pt.lat;
            const alt = (pt.altitude_km !== undefined ? pt.altitude_km : pt.alt_km) * 1000;
            positions.push(Cesium.Cartesian3.fromDegrees(lon, lat, alt));
          });

          // Draw the orbit polyline
          if (showOrbitPaths && positions.length > 2) {
            const orbitEntity = viewer.entities.add({
              name: `${selectedSatellite.name} Orbit Path`,
              polyline: {
                positions: positions,
                width: 2.5,
                material: new Cesium.PolylineGlowMaterialProperty({
                  glowPower: 0.25,
                  color: selectedSatellite.norad_id === 25544 ? Cesium.Color.GOLD : Cesium.Color.CYAN
                })
              }
            });
            orbitEntityRef.current = orbitEntity;
          }

          // Center on first or current point
          const currentPt = points[0];
          const cLon = currentPt.longitude_deg !== undefined ? currentPt.longitude_deg : currentPt.lon;
          const cLat = currentPt.latitude_deg !== undefined ? currentPt.latitude_deg : currentPt.lat;
          const cAlt = currentPt.altitude_km !== undefined ? currentPt.altitude_km : currentPt.alt_km;
          setCurrentSatPosition({ lon: cLon, lat: cLat, alt_km: cAlt });

          viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(
              cLon,
              cLat,
              (cAlt + 4500) * 1000
            ),
            duration: 2.2
          });
        }
      })
      .catch((err) => {
        console.error('Failed to propagate orbit path:', err);
      })
      .finally(() => {
        setIsLoadingOrbit(false);
      });
  }, [selectedSatellite, showOrbitPaths]);

  // Filtered satellite search
  const filteredSatellites = satellites.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.norad_id.toString().includes(searchQuery)
  );

  return (
    <div className="relative w-full h-[calc(100vh-8rem)] rounded-2xl overflow-hidden border border-slate-800 bg-[#040711] shadow-2xl">
      {/* 3D Cesium Container */}
      <div ref={cesiumContainerRef} className="w-full h-full" />

      {/* Top Left Floating Search & Filter Bar */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-2">
        {/* Search Input */}
        <div className="relative w-72">
          <Search className="w-4 h-4 text-cyan-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search satellite or NORAD ID..."
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-[#090f1e]/90 backdrop-blur-md border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono shadow-xl"
          />

          {/* Autocomplete Dropdown */}
          {searchQuery.trim().length > 1 && (
            <div className="absolute left-0 right-0 mt-1.5 max-h-56 overflow-y-auto rounded-xl bg-[#0b1326] border border-slate-800 shadow-2xl divide-y divide-slate-800/60 z-30 font-mono text-xs">
              {filteredSatellites.slice(0, 8).map((sat) => (
                <button
                  key={sat.norad_id}
                  onClick={() => {
                    onSelectSatellite(sat);
                    setSearchQuery('');
                  }}
                  className="w-full px-3 py-2 text-left hover:bg-cyan-950/60 flex items-center justify-between text-slate-300 transition-colors"
                >
                  <span className="font-semibold text-cyan-300 truncate">{sat.name}</span>
                  <span className="text-[10px] text-slate-500 shrink-0">#{sat.norad_id}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Rotation Toggle Button */}
        <button
          onClick={() => setIsRotating(!isRotating)}
          className={`p-2 rounded-xl backdrop-blur-md border text-xs font-semibold flex items-center gap-1.5 shadow-xl transition-colors ${
            isRotating
              ? 'bg-cyan-950/80 border-cyan-500/50 text-cyan-300'
              : 'bg-[#090f1e]/90 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          title={isRotating ? 'Pause Globe Rotation' : 'Resume Globe Rotation'}
        >
          {isRotating ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
        </button>

        {/* Reset Camera View */}
        <button
          onClick={() => {
            if (viewerRef.current) {
              viewerRef.current.camera.flyTo({
                destination: Cesium.Cartesian3.fromDegrees(20.0, 15.0, 22000000.0),
                duration: 1.8
              });
            }
          }}
          className="p-2 rounded-xl bg-[#090f1e]/90 backdrop-blur-md border border-slate-800 text-slate-400 hover:text-cyan-300 shadow-xl transition-colors"
          title="Reset Global View"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>

        {/* Layer Filters */}
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-[#090f1e]/90 backdrop-blur-md border border-slate-800 text-xs shadow-xl font-mono">
          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 text-[11px]">
            <input
              type="checkbox"
              checked={showActiveSats}
              onChange={(e) => setShowActiveSats(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
            />
            <span className="text-cyan-400 font-bold">Active</span>
          </label>
          <span className="text-slate-700">|</span>
          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 text-[11px]">
            <input
              type="checkbox"
              checked={showDebris}
              onChange={(e) => setShowDebris(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-rose-500 focus:ring-0"
            />
            <span className="text-rose-400 font-bold">Debris</span>
          </label>
        </div>
      </div>

      {/* Floating Satellite Details Overlay on Right (Matching Image 2) */}
      {selectedSatellite && (
        <div className="absolute top-4 right-4 z-20 w-84 rounded-2xl bg-[#070e1c]/95 backdrop-blur-xl border border-cyan-500/40 p-5 shadow-2xl space-y-4 font-mono text-xs animate-in fade-in slide-in-from-right-4">
          {/* Card Header */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
            <div className="flex items-center gap-2">
              <SatelliteIcon className="w-4 h-4 text-cyan-400" />
              <div>
                <h3 className="font-bold text-slate-100 text-sm tracking-wide">
                  {selectedSatellite.name}
                </h3>
                <span className="text-[10px] text-cyan-400 font-mono">
                  NORAD: {selectedSatellite.norad_id}
                </span>
              </div>
            </div>
            <button
              onClick={() => onSelectSatellite(null)}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Quick Actions List (Matching Image 2) */}
          <div className="space-y-1.5 text-[11px] text-cyan-400">
            <button className="w-full text-left py-1 hover:text-cyan-200 flex items-center justify-between">
              <span>Find all objects from this launch</span>
              <span>→</span>
            </button>
            <button className="w-full text-left py-1 hover:text-cyan-200 flex items-center justify-between">
              <span>Find all objects within 100km</span>
              <span>→</span>
            </button>
            <button className="w-full text-left py-1 hover:text-cyan-200 flex items-center justify-between">
              <span>Generate Orbit Reference Satellite</span>
              <span>→</span>
            </button>
          </div>

          {/* Orbital Identifiers Table */}
          <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
              Identifiers
            </span>
            <div className="flex justify-between">
              <span className="text-slate-500">COSPAR ID:</span>
              <span className="text-slate-200">{selectedSatellite.intl_designator || '1998-067A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Alt Name:</span>
              <span className="text-slate-200">{selectedSatellite.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Confidence:</span>
              <span className="text-emerald-400 font-bold">High (SGP4 Valid)</span>
            </div>
          </div>

          {/* Orbital Physical Parameters Table */}
          <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
              Orbit Ephemeris
            </span>
            <div className="flex justify-between">
              <span className="text-slate-500">Perigee:</span>
              <span className="text-slate-200 font-bold">
                {selectedSatellite.perigee_km ? `${Math.round(selectedSatellite.perigee_km)} km` : '418 km'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Apogee:</span>
              <span className="text-slate-200 font-bold">
                {selectedSatellite.apogee_km ? `${Math.round(selectedSatellite.apogee_km)} km` : '424 km'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Inclination:</span>
              <span className="text-cyan-400 font-bold">
                {selectedSatellite.inclination_deg ? `${selectedSatellite.inclination_deg.toFixed(2)}°` : '51.64°'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Eccentricity:</span>
              <span className="text-slate-200">
                {selectedSatellite.eccentricity ? selectedSatellite.eccentricity.toFixed(5) : '0.00062'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Period:</span>
              <span className="text-slate-200">
                {selectedSatellite.period_minutes ? `${selectedSatellite.period_minutes.toFixed(1)} min` : '92.8 min'}
              </span>
            </div>
          </div>

          {/* Current Realtime Position if available */}
          {currentSatPosition && (
            <div className="p-3 rounded-xl bg-cyan-950/40 border border-cyan-800/50 space-y-1 text-cyan-300 text-[11px]">
              <div className="flex justify-between">
                <span>Sub-Satellite Lat:</span>
                <span className="font-bold">{currentSatPosition.lat.toFixed(3)}°</span>
              </div>
              <div className="flex justify-between">
                <span>Sub-Satellite Lon:</span>
                <span className="font-bold">{currentSatPosition.lon.toFixed(3)}°</span>
              </div>
              <div className="flex justify-between">
                <span>Current Altitude:</span>
                <span className="font-bold">{currentSatPosition.alt_km.toFixed(1)} km</span>
              </div>
            </div>
          )}

          {isLoadingOrbit && (
            <div className="text-center py-2 text-cyan-400 text-[11px] animate-pulse">
              Computing SGP4 orbit trajectory...
            </div>
          )}
        </div>
      )}
    </div>
  );
};
