import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar, type NavTab } from './components/layout/Sidebar';
import { MissionControl } from './components/dashboard/MissionControl';
import { OrbitalExplorer } from './components/orbital/OrbitalExplorer';
import { IntelligenceCenter } from './components/ai/IntelligenceCenter';
import { CollisionRiskCenter } from './components/risk/CollisionRiskCenter';
import { SimulationLab } from './components/simulation/SimulationLab';
import Aurora from './components/reactbits/Aurora';
import { apiService } from './services/api';
import type { SatelliteSummary, ConjunctionSummary, AgentProposal, SystemHealthStatus } from './types';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [satellites, setSatellites] = useState<SatelliteSummary[]>([]);
  const [conjunctions, setConjunctions] = useState<ConjunctionSummary[]>([]);
  const [proposals, setProposals] = useState<AgentProposal[]>([]);
  const [health, setHealth] = useState<SystemHealthStatus | null>(null);
  const [selectedSatellite, setSelectedSatellite] = useState<SatelliteSummary | null>(null);
  const [selectedConjunction, setSelectedConjunction] = useState<ConjunctionSummary | null>(null);

  const loadData = useCallback(async () => {
    const [healthData, catalogRes, conjData, propData] = await Promise.allSettled([
      apiService.getHealth(),
      apiService.searchCatalog('', 2500),
      apiService.getConjunctions(200),
      apiService.getPendingProposals()
    ]);

    if (healthData.status === 'fulfilled') setHealth(healthData.value);
    if (catalogRes.status === 'fulfilled') {
      const sats = catalogRes.value.data || [];
      setSatellites(sats);
      setSelectedSatellite((prev) => {
        if (sats.length === 0) return null;
        return sats.find((s) => s.norad_id === prev?.norad_id) ?? sats[0];
      });
    }
    if (conjData.status === 'fulfilled') setConjunctions(conjData.value);
    if (propData.status === 'fulfilled') setProposals(propData.value);
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, [loadData]);

  const refreshProposals = () => {
    apiService.getPendingProposals().then(setProposals).catch(console.error);
  };

  const activeAlertsCount = conjunctions.filter(
    (c) => c.risk_tier === 'CRITICAL' || c.risk_tier === 'HIGH'
  ).length;

  return (
    <div className="relative isolate min-h-screen overflow-hidden bg-[#050811] text-slate-100 antialiased">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[360px] opacity-40" aria-hidden="true">
        <Aurora
          colorStops={['#0ea5e9', '#6366f1', '#22d3ee']}
          amplitude={0.8}
          blend={0.7}
          speed={0.3}
          height={0.35}
          scale={1.15}
          glow={0.35}
          layers={2}
          dpr={1}
          className="h-full w-full"
          style={{ maskImage: 'linear-gradient(to bottom, black 0%, transparent 100%)' }}
        />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col">
        <Header
          health={health}
          activeAlertsCount={activeAlertsCount}
          onAlertsClick={() => setCurrentTab('risk')}
        />

        <div className="flex flex-1 overflow-hidden">
          <Sidebar
            currentTab={currentTab}
            onTabChange={setCurrentTab}
            activeAlertsCount={activeAlertsCount}
            pendingApprovalsCount={proposals.length}
            health={health}
          />

        <main className="flex-1 overflow-y-auto p-6">
          {currentTab === 'dashboard' && (
            <MissionControl
              satellites={satellites}
              conjunctions={conjunctions}
              health={health}
              selectedSatellite={selectedSatellite}
              onSelectSatellite={(sat) => setSelectedSatellite(sat)}
              onNavigateToRisk={() => setCurrentTab('risk')}
              onNavigateToExplorer={() => setCurrentTab('orbital')}
              onRefresh={loadData}
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
              conjunctions={conjunctions}
              selectedSatellite={selectedSatellite}
              onProposalDecided={refreshProposals}
            />
          )}

          {currentTab === 'risk' && (
            <CollisionRiskCenter
              conjunctions={conjunctions}
              satellites={satellites}
              onRefresh={loadData}
              onSelectConjunctionForSimulation={(conjunction) => {
                setSelectedConjunction(conjunction);
                setCurrentTab('simulation');
              }}
            />
          )}

          {currentTab === 'simulation' && (
            <SimulationLab
              satellites={satellites}
              conjunctions={conjunctions}
              initialConjunction={selectedConjunction}
            />
          )}
        </main>
        </div>
      </div>
    </div>
  );
};

export default App;
