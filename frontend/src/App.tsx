import React, { useState, useEffect, useCallback } from 'react';
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
    <div className="min-h-screen bg-[#050811] text-slate-100 flex flex-col antialiased">
      <Header
        health={health}
        activeAlertsCount={activeAlertsCount}
        onAlertsClick={() => setCurrentTab('risk')}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          activeAlertsCount={activeAlertsCount}
          pendingApprovalsCount={proposals.length}
          health={health}
        />

        <main className="flex-1 overflow-y-auto p-6 bg-gradient-to-br from-[#060a14] via-[#080d1c] to-[#04060e]">
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
  );
};

export default App;
