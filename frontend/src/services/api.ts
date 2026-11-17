import axios from 'axios';
import type {
  SystemHealthStatus,
  SatelliteSummary,
  ConjunctionSummary,
  AgentProposal,
  AgentMemoryEntry,
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
      data: items
    };
  },

  async getSatellite(norad_id: number): Promise<SatelliteSummary> {
    const res = await apiClient.get(`/catalog/${norad_id}`);
    return res.data;
  },

  // SGP4 Propagation
  async getSatelliteOrbitPath(norad_id: number, duration_hours: number = 1.6, step_minutes: number = 2): Promise<any> {
    const res = await apiClient.get(`/propagation/${norad_id}/orbit`, {
      params: { duration_hours, step_minutes }
    });
    return res.data;
  },

  async getSatelliteCurrentPosition(norad_id: number): Promise<any> {
    const res = await apiClient.get(`/propagation/${norad_id}/current`);
    return res.data;
  },

  // Conjunctions & Risk
  async getConjunctions(limit: number = 50): Promise<ConjunctionSummary[]> {
    try {
      const res = await apiClient.get('/conjunctions', { params: { limit } });
      return Array.isArray(res.data) ? res.data : (res.data.conjunctions || []);
    } catch {
      return [];
    }
  },

  async screenConjunctions(params: { primary_norad_id?: number; threshold_km?: number; time_window_hours?: number }): Promise<any> {
    const res = await apiClient.post('/conjunctions/screen', params);
    return res.data;
  },

  async calculateCollisionProbability(payload: {
    primary_r: number[];
    primary_v: number[];
    secondary_r: number[];
    secondary_v: number[];
    hard_body_radius_m?: number;
  }): Promise<any> {
    const res = await apiClient.post('/collision/calculate-probability', payload);
    return res.data;
  },

  async generateExplainabilityReport(payload: {
    primary_norad_id: number;
    primary_name: string;
    secondary_norad_id: number;
    secondary_name: string;
    tca: string;
    miss_distance_km: number;
    relative_velocity_kms: number;
    collision_probability: number;
    nasa_cara_tier: string;
    b_plane_xi_km: number;
    b_plane_zeta_km: number;
    recommended_burn_direction?: string;
    delta_v_ms?: number;
    fuel_mass_kg?: number;
  }): Promise<{ report_text: string; generated_at: string }> {
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
      return Array.isArray(res.data) ? res.data : [];
    } catch {
      return [];
    }
  },

  async decideProposal(proposal_id: string, decision: 'APPROVED' | 'REJECTED', notes: string = ''): Promise<AgentProposal> {
    const res = await apiClient.post(`/agents/proposals/${proposal_id}/decision`, {
      decision,
      notes
    });
    return res.data;
  },

  async getAgentMemory(limit: number = 20): Promise<AgentMemoryEntry[]> {
    try {
      const res = await apiClient.get('/agents/memory', { params: { limit } });
      return Array.isArray(res.data) ? res.data : [];
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
    semi_major_axis_km?: number;
    spacecraft_dry_mass_kg?: number;
    spacecraft_propellant_mass_kg?: number;
    thruster_isp_seconds?: number;
  }): Promise<ManeuverCandidate[]> {
    const res = await apiClient.post('/simulation/candidates', payload);
    return Array.isArray(res.data) ? res.data : [];
  },

  async compareTrajectories(payload: {
    delta_v_radial_ms: number;
    delta_v_in_track_ms: number;
    delta_v_cross_track_ms: number;
    initial_miss_distance_km: number;
    semi_major_axis_km?: number;
    lead_time_hours?: number;
    num_steps?: number;
  }): Promise<TrajectoryComparisonResult> {
    const res = await apiClient.post('/simulation/compare-trajectories', payload);
    return res.data;
  },

  async runHypotheticalScenario(payload: any): Promise<HypotheticalScenarioResponse> {
    const res = await apiClient.post('/simulation/scenarios/run', payload);
    return res.data;
  },

  // ML Intelligence
  async getMLSummary(norad_id: number): Promise<any> {
    try {
      const res = await apiClient.get(`/ml/summary/${norad_id}`);
      return res.data;
    } catch {
      return null;
    }
  }
};
