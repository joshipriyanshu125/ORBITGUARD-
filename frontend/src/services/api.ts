import axios from 'axios';
import type {
  SystemHealthStatus,
  SatelliteSummary,
  ConjunctionSummary,
  AgentProposal,
  AgentMemoryEntry,
  ExplainabilityReport,
  ManeuverCandidate,
  TrajectoryComparisonResult,
  HypotheticalScenarioResponse
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 45000
});

const normalizeSatellite = (raw: any): SatelliteSummary => ({
  ...raw,
  intl_designator: raw.intl_designator || raw.omm?.OBJECT_ID || undefined,
  period_minutes: raw.period_minutes ?? raw.period_min ?? undefined,
  line1: raw.line1 ?? raw.tle_line1,
  line2: raw.line2 ?? raw.tle_line2,
  object_type: raw.object_type || 'UNKNOWN'
});

const normalizeConjunction = (raw: any): ConjunctionSummary => ({
  ...raw,
  conjunction_id: raw.conjunction_id ?? raw.event_id,
  relative_speed_kms: raw.relative_speed_kms ?? raw.relative_velocity_kms ?? 0,
  risk_tier: raw.risk_tier ?? raw.risk_level,
  risk_score: raw.risk_score,
  created_at: raw.created_at ?? raw.updated_at ?? raw.tca
});

const normalizeProposal = (raw: any): AgentProposal => ({
  ...raw,
  proposal_id: raw.proposal_id ?? raw._id,
  delta_v_ms: raw.delta_v_ms ?? raw.proposed_delta_v_ms,
  post_maneuver_miss_km: raw.post_maneuver_miss_km ?? raw.projected_miss_distance_km,
  fuel_consumption_kg: raw.fuel_consumption_kg,
  requires_human_approval: raw.requires_human_approval ?? true
});

export const apiService = {
  // System Health
  async getHealth(): Promise<SystemHealthStatus> {
    const res = await apiClient.get('/health');
    return res.data;
  },

  // Satellite Catalog
  async searchCatalog(query: string = '', limit: number = 50, skip: number = 0): Promise<{ count: number; data: SatelliteSummary[] }> {
    const res = await apiClient.get('/catalog', {
      params: { q: query, limit, skip }
    });
    const items = Array.isArray(res.data) ? res.data : (res.data.items || res.data.data || []);
    return {
      count: res.data.total || items.length,
      data: items.map(normalizeSatellite)
    };
  },

  async getSatellite(norad_id: number): Promise<SatelliteSummary> {
    const res = await apiClient.get(`/catalog/${norad_id}`);
    return normalizeSatellite(res.data);
  },

  async syncCatalog(groups: string[] = ['stations', 'fengyun-1c-debris']): Promise<any> {
    const query = groups.map((g) => `groups=${encodeURIComponent(g)}`).join('&');
    // Full group sync walks thousands of records; allow well beyond the default timeout.
    const res = await apiClient.post(`/catalog/sync?${query}`, null, { timeout: 600000 });
    return res.data;
  },

  // SGP4 Propagation
  async getSatelliteOrbitPath(norad_id: number, duration_hours: number = 1.6, step_seconds: number = 120): Promise<any> {
    const res = await apiClient.get(`/propagation/${norad_id}/orbit`, {
      params: { duration_hours, step_seconds }
    });
    return res.data;
  },

  async getSatelliteCurrentPosition(norad_id: number): Promise<any> {
    const res = await apiClient.get(`/propagation/${norad_id}/current`);
    return res.data;
  },

  async getCatalogPositions(norad_ids: number[]): Promise<{ timestamp: string; count: number; items: Array<{ norad_id: number; name: string; object_type: string; lat: number; lon: number; alt_km: number }> }> {
    const res = await apiClient.post('/propagation/positions', { norad_ids });
    return res.data;
  },

  // Conjunctions & Risk
  async getConjunctions(limit: number = 50): Promise<ConjunctionSummary[]> {
    try {
      const res = await apiClient.get('/conjunctions', { params: { limit } });
      const items = Array.isArray(res.data) ? res.data : (res.data.items || []);
      return items.map(normalizeConjunction);
    } catch {
      return [];
    }
  },

  async screenConjunctions(params: { primary_norad_id: number; threshold_km?: number; horizon_hours?: number; altitude_margin_km?: number }): Promise<any> {
    const res = await apiClient.post('/conjunctions/screen', params);
    return res.data;
  },

  async getCollisionReport(event_id: string): Promise<ExplainabilityReport> {
    const res = await apiClient.get(`/collision-assessment/report/${encodeURIComponent(event_id)}`);
    return res.data;
  },

  async generateExplainabilityReport(payload: {
    primary_norad_id: number;
    secondary_norad_id: number;
    event_id?: string;
    tca?: string;
    primary_name?: string;
    secondary_name?: string;
    secondary_type?: string;
  }): Promise<{ event_id: string; report_text: string; generated_at: string }> {
    const res = await apiClient.post('/collision/explainability-report', payload);
    return res.data;
  },

  // Autonomous Agents & Orchestrator
  async orchestrateMission(payload: {
    goal: string;
    conjunction_id?: string;
    target_norad_id?: number;
  }): Promise<any> {
    const res = await apiClient.post('/agents/orchestrate', payload);
    return res.data;
  },

  async getPendingProposals(): Promise<AgentProposal[]> {
    try {
      const res = await apiClient.get('/agents/proposals/pending');
      const items = Array.isArray(res.data) ? res.data : [];
      return items.map(normalizeProposal);
    } catch {
      return [];
    }
  },

  async decideProposal(proposal_id: string, decision: 'APPROVED' | 'REJECTED', operator_name: string, notes: string = ''): Promise<any> {
    const res = await apiClient.post(`/agents/proposals/${proposal_id}/decision`, {
      decision,
      operator_name,
      notes
    });
    return res.data;
  },

  async getAgentMemory(limit: number = 20): Promise<AgentMemoryEntry[]> {
    try {
      const res = await apiClient.get('/agents/memory', { params: { limit } });
      const docs = Array.isArray(res.data) ? res.data : [];
      return docs.map((m: any) => ({
        memory_id: m.session_id,
        agent_role: `Session ${m.session_id}`,
        session_id: m.session_id,
        task_summary: m.query ?? '',
        findings: { summary: m.findings_summary ?? '', steps: m.plan?.steps ?? [] },
        created_at: m.created_at,
      }));
    } catch {
      return [];
    }
  },

  // Simulation Laboratory
  async getSimulationPresets(): Promise<any[]> {
    const res = await apiClient.get('/simulation/scenarios/presets');
    return res.data.presets || [];
  },

  async generateManeuverCandidates(payload: {
    initial_miss_distance_km: number;
    desired_miss_distance_km: number;
    relative_velocity_kms: number;
    lead_time_hours: number;
    semi_major_axis_km: number;
    spacecraft_dry_mass_kg: number;
    spacecraft_propellant_mass_kg: number;
    thruster_isp_seconds: number;
  }): Promise<ManeuverCandidate[]> {
    const res = await apiClient.post('/simulation/candidates', payload);
    return Array.isArray(res.data) ? res.data : [];
  },

  async compareTrajectories(payload: {
    delta_v_radial_ms: number;
    delta_v_in_track_ms: number;
    delta_v_cross_track_ms: number;
    initial_miss_distance_km: number;
    semi_major_axis_km: number;
    lead_time_hours: number;
    spacecraft_dry_mass_kg: number;
    spacecraft_propellant_mass_kg: number;
    thruster_isp_seconds: number;
    num_steps?: number;
  }): Promise<TrajectoryComparisonResult> {
    const res = await apiClient.post('/simulation/compare-trajectories', payload);
    return res.data;
  },

  async runHypotheticalScenario(payload: any): Promise<HypotheticalScenarioResponse> {
    const res = await apiClient.post('/simulation/scenarios/run', payload);
    return res.data;
  }
};
