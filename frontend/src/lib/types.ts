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
