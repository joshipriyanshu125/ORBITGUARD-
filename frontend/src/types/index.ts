export interface SatelliteSummary {
  norad_id: number;
  name: string;
  intl_designator?: string;
  epoch?: string;
  inclination_deg?: number;
  raan_deg?: number;
  eccentricity?: number;
  arg_perigee_deg?: number;
  mean_anomaly_deg?: number;
  mean_motion_rev_day?: number;
  semi_major_axis_km?: number;
  period_minutes?: number;
  perigee_km?: number;
  apogee_km?: number;
  line1?: string;
  line2?: string;
  decay_date?: string | null;
  object_type?: 'PAYLOAD' | 'ROCKET_BODY' | 'DEBRIS' | 'UNKNOWN';
}

export interface SatellitePosition {
  norad_id: number;
  name: string;
  timestamp: string;
  lat: number;
  lon: number;
  alt_km: number;
  x_eci: number;
  y_eci: number;
  z_eci: number;
  vx: number;
  vy: number;
  vz: number;
  velocity_kms: number;
}

export interface ConjunctionSummary {
  conjunction_id: string;
  primary_norad_id: number;
  primary_name: string;
  secondary_norad_id: number;
  secondary_name: string;
  tca: string;
  miss_distance_km: number;
  relative_speed_kms: number;
  collision_probability?: number;
  collision_probability_sci?: string;
  risk_tier?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NOMINAL';
  nasa_cara_tier?: string;
  b_plane_xi_km?: number;
  b_plane_zeta_km?: number;
  upi_score?: number;
  created_at: string;
}

export interface AgentProposal {
  proposal_id: string;
  conjunction_id: string;
  target_norad_id: number;
  target_name?: string;
  burn_type: string;
  burn_direction: string;
  burn_epoch: string;
  delta_v_ms: number;
  delta_v_vector_lvlh?: number[];
  post_maneuver_miss_km: number;
  post_maneuver_pc?: number;
  fuel_consumption_kg: number;
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED';
  requires_human_approval: boolean;
  operator_notes?: string;
  created_at: string;
}

export interface AgentMemoryEntry {
  memory_id: string;
  agent_role: string;
  session_id: string;
  task_summary: string;
  findings: Record<string, any>;
  created_at: string;
}

export interface ManeuverCandidate {
  candidate_id: string;
  name: string;
  maneuver_type: string;
  burn_direction: string;
  delta_v_ms: number;
  delta_v_vector_lvlh: number[];
  burn_epoch: string;
  lead_time_to_tca_hours: number;
  projected_miss_distance_km: number;
  post_maneuver_collision_prob: number;
  post_maneuver_collision_prob_sci: string;
  post_maneuver_cara_tier: string;
  fuel_mass_kg: number;
  fuel_efficiency_km_per_kg: number;
  residual_fuel_budget_kg: number;
  secondary_conjunction_risk: string;
  recommendation_rank: number;
  tradeoff_rationale: string;
}

export interface TrajectoryPoint {
  time: string;
  time_offset_seconds: number;
  baseline_eci: number[];
  maneuvered_eci: number[];
  separation_delta_km: number;
  radial_delta_km: number;
  in_track_delta_km: number;
  cross_track_delta_km: number;
  baseline_altitude_km: number;
  maneuvered_altitude_km: number;
}

export interface TrajectoryComparisonResult {
  candidate_id: string;
  maneuver_name: string;
  delta_v_ms: number;
  tca: string;
  baseline_miss_distance_km: number;
  post_burn_miss_distance_km: number;
  miss_distance_gain_km: number;
  max_spatial_separation_km: number;
  tca_radial_separation_km: number;
  tca_in_track_separation_km: number;
  tca_cross_track_separation_km: number;
  trajectory_points: TrajectoryPoint[];
}

export interface HypotheticalScenarioResponse {
  scenario_id: string;
  scenario_type: string;
  scenario_name: string;
  scenario_description: string;
  baseline_encounter: {
    initial_miss_distance_km: number;
    relative_velocity_kms: number;
    lead_time_hours: number;
    spacecraft_total_mass_kg: number;
    thruster_isp_seconds: number;
  };
  candidates_evaluated: ManeuverCandidate[];
  optimal_candidate: ManeuverCandidate;
  fuel_comparison_table: Array<{
    candidate_id: string;
    strategy: string;
    delta_v_ms: number;
    propellant_consumed_kg: number;
    post_burn_miss_km: number;
    efficiency_km_per_kg: number;
    residual_fuel_kg: number;
    cara_tier: string;
    within_budget: boolean;
  }>;
  trajectory_comparison: TrajectoryComparisonResult;
  secondary_risk_check: {
    status: string;
    screened_catalog_objects: number;
    secondary_encounters_detected: number;
    cleared_safety_corridor_km: number;
    risk_assessment: string;
  };
  executive_engineering_debrief: string;
}

export interface SystemHealthStatus {
  service: string;
  status: string;
  version: string;
  environment: string;
  timestamp: string;
  database: {
    status: string;
    database: string;
    collections: Record<string, number>;
  };
  ingestion_scheduler?: {
    running: boolean;
    interval_hours: number;
  };
}
