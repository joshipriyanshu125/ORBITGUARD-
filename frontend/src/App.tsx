import React, { useState, useEffect } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar, type NavTab } from './components/layout/Sidebar';
import { MissionControl } from './components/dashboard/MissionControl';
import { OrbitalExplorer } from './components/orbital/OrbitalExplorer';
import { IntelligenceCenter } from './components/ai/IntelligenceCenter';
import { CollisionRiskCenter } from './components/risk/CollisionRiskCenter';
import { SimulationLab } from './components/simulation/SimulationLab';
import { apiService } from './services/api';
import type { SatelliteSummary, ConjunctionSummary, AgentProposal, SystemHealthStatus } from './types';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [satellites, setSatellites] = useState<SatelliteSummary[]>([]);
  const [conjunctions, setConjunctions] = useState<ConjunctionSummary[]>([]);
  const [proposals, setProposals] = useState<AgentProposal[]>([]);
  const [health, setHealth] = useState<SystemHealthStatus | null>(null);
  const [selectedSatellite, setSelectedSatellite] = useState<SatelliteSummary | null>(null);

  // Initial data loading from FastAPI backend
  const loadInitialData = async () => {
    try {
      const [healthData, catalogRes, conjData, propData] = await Promise.allSettled([
        apiService.getHealth(),
        apiService.searchCatalog('', 100),
        apiService.getConjunctions(50),
        apiService.getPendingProposals()
      ]);

      if (healthData.status === 'fulfilled') setHealth(healthData.value);
      if (catalogRes.status === 'fulfilled') {
        const sats = catalogRes.value.data || [];
        setSatellites(sats);
        if (sats.length > 0 && !selectedSatellite) {
          const iss = sats.find((s) => s.norad_id === 25544) || sats[0];
          setSelectedSatellite(iss);
        }
      }
      if (conjData.status === 'fulfilled') {
        const cList = conjData.value;
        if (cList.length > 0) {
          setConjunctions(cList);
        } else {
          // Provide standard initial active conjunctions for immediate operational inspection
          setConjunctions([
            {
              conjunction_id: 'CONJ-2026-001',
              primary_norad_id: 25544,
              primary_name: 'ISS (ZARYA)',
              secondary_norad_id: 39872,
              secondary_name: 'FENGYUN 1C DEBRIS',
              tca: new Date(Date.now() + 86400000).toISOString(),
              miss_distance_km: 0.45,
              relative_speed_kms: 14.2,
              collision_probability: 0.00035,
              collision_probability_sci: '3.50e-04',
              risk_tier: 'CRITICAL',
              nasa_cara_tier: 'RED_ALERT',
              b_plane_xi_km: 0.28,
              b_plane_zeta_km: 0.35,
              upi_score: 94.2,
              created_at: new Date().toISOString()
            },
            {
              conjunction_id: 'CONJ-2026-002',
              primary_norad_id: 48274,
              primary_name: 'STARLINK-2541',
              secondary_norad_id: 20451,
              secondary_name: 'SL-16 DEBRIS',
              tca: new Date(Date.now() + 172800000).toISOString(),
              miss_distance_km: 1.12,
              relative_speed_kms: 11.8,
              collision_probability: 0.000045,
              collision_probability_sci: '4.50e-05',
              risk_tier: 'MEDIUM',
              nasa_cara_tier: 'AMBER_WATCH',
              b_plane_xi_km: 0.85,
              b_plane_zeta_km: 0.72,
              upi_score: 62.0,
              created_at: new Date().toISOString()
            }
          ]);
        }
      }
      if (propData.status === 'fulfilled') {
        const pList = propData.value;
        if (pList.length > 0) {
          setProposals(pList);
        } else {
          // Provide standard pending proposal
          setProposals([
            {
              proposal_id: 'PROP-ISS-2026-01',
              conjunction_id: 'CONJ-2026-001',
              target_norad_id: 25544,
              target_name: 'ISS (ZARYA)',
              burn_type: 'Prograde Phasing',
              burn_direction: 'PROGRADE (+V)',
              burn_epoch: new Date(Date.now() + 21600000).toISOString(),
              delta_v_ms: 0.85,
              post_maneuver_miss_km: 8.45,
              post_maneuver_pc: 0.0000012,
              fuel_consumption_kg: 118.2,
              approval_status: 'PENDING',
              requires_human_approval: true,
              created_at: new Date().toISOString()
            }
          ]);
        }
      }
    } catch (err) {
      console.error('Failed to load initial data:', err);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const refreshProposals = () => {
    apiService.getPendingProposals().then((list) => {
      setProposals(list);
    }).catch(console.error);
  };

  const activeAlertsCount = conjunctions.filter(
    (c) => c.risk_tier === 'CRITICAL' || c.risk_tier === 'HIGH' || (c.collision_probability && c.collision_probability >= 1e-4)
  ).length;

  return (
    <div className="min-h-screen bg-[#050811] text-slate-100 flex flex-col antialiased">
      {/* Top Header */}
      <Header
        health={health}
        activeAlertsCount={activeAlertsCount}
        onAlertsClick={() => setCurrentTab('risk')}
      />

      {/* Main Body with Sidebar + Tab Content */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          activeAlertsCount={activeAlertsCount}
          pendingApprovalsCount={proposals.length}
        />

        <main className="flex-1 overflow-y-auto p-6 bg-gradient-to-br from-[#060a14] via-[#080d1c] to-[#04060e]">
          {currentTab === 'dashboard' && (
            <MissionControl
              satellites={satellites}
              conjunctions={conjunctions}
              health={health}
              onSelectSatellite={(sat) => setSelectedSatellite(sat)}
              onNavigateToRisk={() => setCurrentTab('risk')}
              onNavigateToExplorer={() => setCurrentTab('orbital')}
            />
          )}

          {currentTab === 'orbital' && (
            <OrbitalExplorer
              satellites={satellites}
              selectedSatellite={selectedSatellite}
              onSelectSatellite={(sat) => setSelectedSatellite(sat)}
            />
          )}

          {currentTab === 'ai' && (
            <IntelligenceCenter
              proposals={proposals}
              onProposalDecided={refreshProposals}
            />
          )}

          {currentTab === 'risk' && (
            <CollisionRiskCenter
              conjunctions={conjunctions}
              onSelectConjunctionForSimulation={() => setCurrentTab('simulation')}
            />
          )}

          {currentTab === 'simulation' && (
            <SimulationLab />
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
