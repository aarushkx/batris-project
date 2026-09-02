/**
 * Shapes returned by the FastAPI backend.
 *
 * These types match the data returned by the backend assessment and model
 * modules. Nullable fields are used when the backend can return `null`.
 */

export interface BatterySummary {
  battery_id: string;
  format_key: string;
  cycles: number;
  first_cycle: number;
  last_cycle: number;
  measured_soh_range: [number, number];
}

export interface BatteryFormat {
  key: string;
  display_name: string;
  chemistry: string;
  form_factor: string;
  rated_capacity_ah: number;
  nominal_voltage_v: number;
  v_max: number;
  v_min: number;
  v_min_absolute: number;
  cells_in_series: number;
  cells_in_parallel: number;
  max_charge_c_rate: number;
  max_discharge_c_rate: number;
  temp_warn_c: number;
  temp_critical_c: number;
  temp_max_charge_c: number;
  temp_min_charge_c: number;
  eol_soh: number;
  second_life_floor_soh: number;
}

export interface HealthEstimate {
  soh: number;
  soh_percent: number;
  confidence_interval_90: [number, number];
  interval_width: number;
  state_of_health_label: string;
  remaining_capacity_ah: number;
  eol_threshold: number;
  past_first_life_eol: boolean;
  fade_rate_soh_points_per_100_cycles: number | null;
  [key: string]: unknown;
}

export interface Signal {
  signal: string;
  feature: string;
  measured_value: number | null;
  impact_soh_percentage_points: number;
}

export interface DegradationFactor {
  factor: string;
  label: string;
  impact_soh_percentage_points: number;
  share_of_explanation: number;
  direction: string;
  mechanism: string;
  narrative: string;
  top_signals: Signal[];
}

export interface Anomaly {
  code: string;
  severity: "critical" | "warning" | "info" | string;
  detail: string;
  source: string;
  evidence: Record<string, number>;
}

export interface AnomalySummary {
  anomaly_score: number;
  max_severity: string;
  is_anomalous: boolean;
  n_anomalies: number;
  anomalies: Anomaly[];
  isolation_score: number;
  trajectory_residual: number;
  detectors_run: Record<string, boolean>;
  coverage_note?: string | null;
  recent_window_cycles?: number;
  recent_anomalous_cycles?: number;
  recent_critical_cycles?: number;
}

export interface RiskDriver {
  factor: string;
  contribution: number;
  finding: string;
}

export interface ChargingEnvelope {
  max_charge_c_rate: number;
  max_charge_current_a: number;
  derating_applied: number;
  recommended_soc_window_percent: [number, number];
  charge_voltage_setpoint_v: number | null;
  charge_voltage_setpoint_note: string;
  soc_guidance: string;
  charge_temperature_window_c: [number, number];
  absolute_limits: {
    v_max: number;
    v_min_recommended: number;
    v_min_absolute: number;
    temp_critical_c: number;
  };
}

export type Priority = "urgent" | "advised" | "routine";

export interface Recommendation {
  category: string;
  priority: Priority;
  action: string;
  rationale: string;
}

export interface SafetyAssessment {
  risk_score: number;
  risk_band: "LOW" | "MODERATE" | "HIGH" | string;
  band_meaning: string;
  risk_drivers: RiskDriver[];
  safe_charging_envelope: ChargingEnvelope;
  recommendations: Recommendation[];
}

export interface SecondLife {
  grade: string;
  recommendation: string;
  rationale: string;
  grading_basis: string;
  grading_basis_soh: number;
  grade_confidence: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN" | string;
  grade_is_ambiguous: boolean;
  worst_case_grade: string;
  best_case_grade: string;
  confidence_interval_width_soh_points: number | null;
  next_step: string;
  safety_override_applied: boolean;
  estimated_remaining_energy_wh: number;
}

export interface ReferenceMeasurement {
  method: string;
  method_description: string;
  measured_capacity_ah: number;
  measured_soh: number;
  estimation_error_percentage_points: number;
  within_confidence_interval: boolean;
}

export interface ModelProvenance {
  soh_model_variant: string;
  soh_features_used: number;
  training_batteries: string[] | null;
  training_cycles: number | null;
  training_data_sha256: string | null;
  interval_calibration_factor: number;
  validation_method: string;
  validation_mae_soh_points: number | null;
  anomaly_detector_threshold?: number;
  input_tier?: string;
  training_chemistries?: string[];
  cross_chemistry_interval_factor?: number;
  validation_r2?: number | null;
  validation_worst_battery_mae_soh_points?: number | null;
}

export interface Trajectory {
  /** Set by the assessment API; omitted when a chart is built client-side. */
  method?: string;
  description?: string;
  /** Per-cycle ISO timestamps, used to date health-timeline events. */
  timestamp?: (string | null)[];
  cycle_index: number[];
  estimated_soh: number[];
  measured_soh: (number | null)[];
  anomaly_score: number[];
  anomalous_cycles: number[];
  peak_temp_c: (number | null)[];
}

export interface Assessment {
  battery_id: string;
  format: BatteryFormat;
  cycle_index: number;
  total_cycles_observed: number;
  timestamp: string;
  health: HealthEstimate;
  degradation_factors: DegradationFactor[];
  degradation_summary: string;
  explanation_caveat: string;
  anomaly: AnomalySummary;
  safety: SafetyAssessment;
  second_life: SecondLife;
  reference_measurement: ReferenceMeasurement | null;
  model_provenance: ModelProvenance;
  trajectory: Trajectory | null;
}

// --------------------------------------------------------------------------
// Onboarding ("assess my own battery")
// --------------------------------------------------------------------------

export interface InputFieldSpec {
  key: string;
  label: string;
  unit: string;
  kind: "number" | "text" | "select" | string;
  required: boolean;
  help: string;
  min: number | null;
  max: number | null;
  placeholder: string;
}

export interface TierSpec {
  key: string;
  rank: number;
  display_name: string;
  description: string;
  source: string;
  n_features: number;
  reliable: boolean;
  fields: InputFieldSpec[];
}

export interface FormatOption {
  key: string;
  display_name: string;
  chemistry: string;
  rated_capacity_ah: number;
  nominal_voltage_v: number;
  in_training_distribution: boolean;
}

export interface OnboardingSchema {
  tiers: TierSpec[];
  manual_tier: string;
  context_fields: InputFieldSpec[];
  formats: FormatOption[];
  trained_chemistries: string[];
  telemetry_columns: string[];
}

export interface TierValidation {
  mae_soh_percentage_points?: number | null;
  r2?: number | null;
  worst_battery_mae_soh_points?: number | null;
  [key: string]: unknown;
}

export interface UnavailableAnalysis {
  analysis: string;
  reason: string;
  how_to_enable: string;
}

export interface ChemistryTransfer {
  in_distribution: boolean;
  interval_factor: number;
  trained_chemistries: string[];
  requested_chemistry: string;
  note: string;
}

export interface UnseenAssessment
  extends Omit<Assessment, "reference_measurement" | "cycle_index"> {
  is_unseen_battery: true;
  cycle_index: number | null;
  input_tier: TierSpec & {
    measured_accuracy: TierValidation;
    interval_calibration_factor: number;
  };
  assumptions: string[];
  chemistry_transfer: ChemistryTransfer;
  unavailable_analyses: UnavailableAnalysis[];
  reference_measurement: Record<string, unknown> | null;
}

// --------------------------------------------------------------------------
// Model info
// --------------------------------------------------------------------------

export interface TierModelInfo {
  key: string;
  rank: number | null;
  display_name: string | null;
  reliable: boolean;
  n_features: number;
  mae_soh_points: number | null;
  r2: number | null;
  worst_battery_mae_soh_points: number | null;
  interval_calibration_factor: number;
}

export interface ModelInfo {
  tiers: TierModelInfo[];
  anomaly_detector?: Record<string, unknown>;
  [variant: string]: unknown;
}

// --------------------------------------------------------------------------
// Passport
// --------------------------------------------------------------------------

export interface Passport {
  payload: {
    battery: { battery_id: string; [key: string]: unknown };
    health_estimate: {
      soh: number;
      soh_percent: number;
      [key: string]: unknown;
    };
    second_life_assessment: { grade: string; [key: string]: unknown };
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface PassportPdf {
  passport_id: string;
  /** Path (relative to the API origin) that serves the generated PDF. */
  pdf_url: string;
}

export interface VerifyResult {
  valid: boolean;
  errors: string[];
  warnings?: string[];
  trust_anchor?: string;
  public_key_fingerprint?: string;
  passport_id?: string;
  health_method?: string;
  certified_test_status?: string;
}

export interface RegisterFormatResult {
  registered: boolean;
  format: BatteryFormat;
  in_training_distribution: boolean;
}

// --------------------------------------------------------------------------
// Benchmark
// --------------------------------------------------------------------------

export interface BenchmarkModelMetrics {
  mae: number;
  rmse: number;
  r2: number;
  max_abs_error: number;
  bias: number;
  mae_soh_points: number;
  rmse_soh_points: number;
  max_error_soh_points: number;
  bias_soh_points: number;
}

/** Per-cycle measured-vs-estimated SOH for one (model, held-out battery) fold. */
export interface BenchmarkTrajectory {
  cycle_index: number[];
  measured_soh: number[];
  estimated_soh: number[];
}

export interface BenchmarkModelResult {
  model_key: string;
  model_display_name: string;
  overall: BenchmarkModelMetrics;
  per_battery: Record<string, BenchmarkModelMetrics>;
  /** Present once the benchmark has been generated with trajectory capture. */
  trajectories?: Record<string, BenchmarkTrajectory>;
}

export interface BenchmarkResults {
  n_cycles: number;
  batteries: string[];
  n_batteries: number;
  features_used: number;
  models: BenchmarkModelResult[];
  best_model: string;
  best_model_display_name: string;
  generated_at: string;
}

// --------------------------------------------------------------------------
// Health timeline
// --------------------------------------------------------------------------

export type TimelineSeverity = "critical" | "warning" | "good" | "info";
export type HealthPhase = "healthy" | "warning" | "critical";

export type TimelineEventKind =
  | "observation_start"
  | "state_change"
  | "milestone"
  | "fade_acceleration"
  | "anomaly_first"
  | "anomaly_cluster"
  | "thermal_excursion"
  | "thermal_clear"
  | "anomaly_finding"
  | "degradation_attribution"
  | "assessment"
  | "projection"
  | "unobserved_history";

export interface TimelineEvent {
  id: string;
  kind: TimelineEventKind | string;
  severity: TimelineSeverity;
  title: string;
  detail: string;
  /** Null for forward-looking entries, which carry no cycle. */
  cycle: number | null;
  date: string | null;
  soh_percent: number | null;
  phase: HealthPhase | null;
  evidence: Record<string, unknown>;
}

export interface TimelinePhase {
  state: string;
  label: string;
  phase: HealthPhase;
  meaning: string;
  from_cycle: number | null;
  to_cycle: number | null;
  duration_cycles: number | null;
  entered_at_soh_percent: number | null;
  entered_on: string | null;
  reuse_grade: string;
  is_current: boolean;
}

export interface TimelineProjection {
  target_label: string;
  target_soh_percent: number;
  fade_points_per_100_cycles: number;
  cycles_remaining: number;
  reference_cycle: number | null;
}

export interface TimelineSummary {
  battery_id: string;
  source: "trajectory" | "snapshot";
  cycles_observed: number | null;
  first_cycle: number | null;
  last_cycle: number | null;
  assessed_at_cycle: number | null;
  soh_at_first_observation_percent: number | null;
  soh_now_percent: number | null;
  soh_points_lost: number | null;
  fade_rate_soh_points_per_100_cycles: number | null;
  current_state: string;
  current_state_label: string;
  current_phase: HealthPhase;
  cycles_in_current_state: number | null;
  reuse_grade: string | null;
  risk_band: string;
  n_events: number;
  n_state_changes: number;
  n_warnings: number;
  n_critical: number;
  n_anomalous_cycles: number;
  first_event_date: string | null;
  last_event_date: string | null;
  headline: string;
  projection: TimelineProjection | null;
}

export interface TimelineSeries {
  cycle_index: number[];
  estimated_soh: (number | null)[];
  measured_soh: (number | null)[];
  anomalous_cycles: number[];
  method: string | null;
}

export interface Timeline {
  battery_id: string;
  generated_at_utc: string;
  format: {
    key: string | null;
    display_name: string | null;
    chemistry: string | null;
    rated_capacity_ah: number | null;
    eol_soh_percent: number;
    second_life_floor_soh_percent: number;
  };
  summary: TimelineSummary;
  states: TimelinePhase[];
  events: TimelineEvent[];
  series: TimelineSeries | null;
  thresholds: {
    as_new_soh_percent: number;
    eol_soh_percent: number;
    grade_b_floor_soh_percent: number;
    reuse_floor_soh_percent: number;
  };
  method_note: string;
}

export interface TimelinePdf {
  timeline_id: string;
  battery_id: string | null;
  /** Path (relative to the API origin) that serves the generated PDF. */
  pdf_url: string;
}

// --------------------------------------------------------------------------
// Second-life market
// --------------------------------------------------------------------------

export type ReuseGrade = "A" | "B" | "C" | "RECYCLE";

export interface MarketSeller {
  name: string;
  email: string;
}

export interface MarketListing {
  listing_id: string;
  status: "active" | "withdrawn" | string;
  battery_id: string;
  title: string | null;
  location: string | null;
  notes: string | null;
  is_reference_fleet: boolean;
  seller: MarketSeller;

  format_key: string | null;
  format_display_name: string | null;
  chemistry: string;
  form_factor: string | null;
  rated_capacity_ah: number | null;
  nominal_voltage_v: number | null;

  soh: number;
  soh_percent: number;
  soh_lower_percent: number | null;
  soh_upper_percent: number | null;
  health_label: string | null;
  retained_capacity_ah: number | null;
  remaining_energy_wh: number | null;
  fade_rate_soh_points_per_100_cycles: number | null;

  grade: ReuseGrade | string;
  grade_recommendation: string | null;
  grade_rationale: string | null;
  grade_confidence: string | null;
  grade_is_ambiguous: boolean;
  worst_case_grade: string | null;
  best_case_grade: string | null;
  next_step: string | null;
  safety_override_applied: boolean;

  risk_band: string | null;
  risk_score: number | null;
  anomaly_max_severity: string | null;
  anomaly_count: number;

  assessed_at_cycle: number | null;
  cycles_observed: number | null;
  assessed_at: string | null;
  has_trajectory: boolean;
  is_unseen_battery: boolean;

  passport_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Detail response: the listing plus the assessment it was derived from. */
export interface MarketListingDetail extends MarketListing {
  assessment: Assessment | null;
  passport: Passport | null;
}

export interface MarketBrowseResult {
  items: MarketListing[];
  counts: Record<string, number>;
  total: number;
  filtered: number;
  chemistries: string[];
  grade_order: string[];
}
