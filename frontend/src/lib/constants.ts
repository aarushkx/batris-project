/** Team identifier carried on issued passports. */
export const TEAM_NAME = "Team Ascend";

// ---------------------------------------------------------------------------
// Product identity
// ---------------------------------------------------------------------------

export const APP_NAME = "BATRIS";
export const APP_FULL_NAME = "Battery Traceability & Reliability Intelligence System";
export const APP_TAGLINE =
  "SOH estimation · degradation analysis · safety · verifiable reuse passport";
export const APP_DESCRIPTION =
  "Estimate the state of health of a lithium-ion battery from ordinary charging data, explain why it is degrading, check it against safety limits, and issue a signed second-life passport anyone can verify.";

export const DATA_SOURCE =
  "NASA Ames Prognostics Center of Excellence battery dataset (Saha & Goebel, 2007)";

export const BUILT_FOR = "Smart India Hackathon";

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

/**
 * All requests go to same-origin `/api/*`, which `next.config.ts` rewrites to
 * the FastAPI server. Keeping it same-origin means no CORS setup is needed.
 */
export const API_BASE = "/api";

export const API_ROUTES = {
  batteries: `${API_BASE}/batteries`,
  formats: `${API_BASE}/formats`,
  modelInfo: `${API_BASE}/model-info`,
  assess: (batteryId: string) => `${API_BASE}/assess/${batteryId}`,
  passport: (batteryId: string) => `${API_BASE}/passport/${batteryId}`,
  passportPdf: `${API_BASE}/passport/pdf`,
  verify: `${API_BASE}/verify`,
  verifyWithIssuerKey: `${API_BASE}/verify?use_issuer_key=true`,
  issuerPublicKey: `${API_BASE}/issuer-public-key`,
  onboardingSchema: `${API_BASE}/onboarding/schema`,
  onboardingAssess: `${API_BASE}/onboarding/assess`,
  onboardingPassport: `${API_BASE}/onboarding/passport`,
  onboardingFormat: `${API_BASE}/onboarding/format`,
  authRegister: `${API_BASE}/auth/register`,
  authLogin: `${API_BASE}/auth/login`,
  authLogout: `${API_BASE}/auth/logout`,
  authMe: `${API_BASE}/auth/me`,
  accountAssessments: `${API_BASE}/account/assessments`,
  accountPassports: `${API_BASE}/account/passports`,
} as const;

// ---------------------------------------------------------------------------
// Model variants
// ---------------------------------------------------------------------------

export const SOH_VARIANTS = [
  {
    value: "full",
    label: "Full",
    hint: "Known history",
    description:
      "Uses the battery's recorded provenance as well as its present telemetry.",
  },
  {
    value: "provenance_free",
    label: "Provenance-free",
    hint: "Unknown history",
    description:
      "Reads only present physical condition. The realistic case for a used pack whose paperwork is missing or untrustworthy.",
  },
] as const;

export type SohVariant = (typeof SOH_VARIANTS)[number]["value"];

export const DEFAULT_VARIANT: SohVariant = "full";

// ---------------------------------------------------------------------------
// Thresholds — mirrors the defaults in backend/batris/formats.py
// ---------------------------------------------------------------------------

/** End of first life. Below this a pack leaves vehicle service. */
export const EOL_SOH = 0.8;

/** Below this reuse is not recommended at all. */
export const SECOND_LIFE_FLOOR_SOH = 0.6;

/** Health bands used to colour the SOH readout. */
export const SOH_BANDS = {
  healthy: 0.8,
  degraded: 0.7,
} as const;

/** Risk-driver contribution above which a driver is treated as urgent. */
export const RISK_DRIVER_URGENT = 45;
export const RISK_DRIVER_ADVISED = 20;

export const RECOMMENDATION_ORDER = {
  urgent: 0,
  advised: 1,
  routine: 2,
} as const;

// ---------------------------------------------------------------------------
// Chart
// ---------------------------------------------------------------------------

export const CHART = {
  width: 1000,
  height: 340,
  margin: { top: 18, right: 20, bottom: 44, left: 56 },
  yPadding: 0.03,
  yTicks: 5,
  xTicks: 6,
  colors: {
    measured: "var(--signal)",
    estimated: "var(--estimated)",
    eol: "var(--ink-soft)",
    anomaly: "var(--warn)",
    marker: "var(--ink)",
    grid: "var(--line)",
    axis: "var(--ink-soft)",
  },
} as const;

export const CHART_LEGEND = [
  { key: "measured", label: "Measured SOH (reference discharge)" },
  { key: "estimated", label: "Estimated SOH (model)" },
  { key: "eol", label: "80% end of first life" },
  { key: "anomaly", label: "Anomalous cycle" },
] as const;

// ---------------------------------------------------------------------------
// Custom battery format registration
// ---------------------------------------------------------------------------

export const CHEMISTRIES = ["NMC", "LFP", "LCO", "LTO", "NCA", "OTHER"] as const;

export const FORM_FACTORS = [
  { value: "cylindrical_pack", label: "Cylindrical pack" },
  { value: "prismatic", label: "Prismatic" },
  { value: "pouch", label: "Pouch" },
  { value: "cylindrical_18650", label: "18650 cell" },
  { value: "cylindrical_21700", label: "21700 cell" },
] as const;

// ---------------------------------------------------------------------------
// "Assess my own battery" — input modes
// ---------------------------------------------------------------------------

export const INPUT_MODES = [
  {
    value: "questionnaire",
    title: "I'll type in numbers from my charger",
    detail: "Tier 3 · 2.86 SOH points measured error",
  },
  {
    value: "telemetry",
    title: "I have a charge log file (CSV)",
    detail: "Tier 1–2 · 2.67–2.75 SOH points measured error",
  },
] as const;

export type InputMode = (typeof INPUT_MODES)[number]["value"];

/**
 * A mid-life 18650: the constant-current phase has shortened and the taper has
 * lengthened, which is the signature of lost lithium inventory.
 */
export const EXAMPLE_QUESTIONNAIRE: Record<string, number> = {
  charge_current_a: 1.5,
  cc_duration_min: 45,
  cv_duration_min: 48,
  total_charge_ah: 1.55,
  peak_temp_c: 34,
  ambient_temp_c: 26,
  cycle_count: 260,
  age_months: 30,
};

export const EXAMPLE_BATTERY_ID = "DEMO-PACK-01";

export const TELEMETRY_CSV_COLUMNS = [
  "time_s",
  "voltage_v",
  "current_a",
  "temperature_c",
] as const;

export const TELEMETRY_CSV_ALIASES = ["time", "voltage", "current", "temp"] as const;

// ---------------------------------------------------------------------------
// Standing copy
// ---------------------------------------------------------------------------

// export const ESTIMATE_BANNER = {
//   title: "Estimate, not a certification.",
//   body: "Every health figure below is produced by a statistical model from operating telemetry. It is not a measured capacity test and carries the uncertainty shown. Binding reuse, warranty or disposal decisions require accredited testing.",
// } as const;
export const ESTIMATE_BANNER = {
  title: "A clearer view of battery health.",
  body: "Health estimates are derived from operating history, cycle behaviour and recorded telemetry to provide an indication of present battery condition. Review the confidence range alongside each result to understand how certain the assessment is.",
} as const;

export const METHOD_TAG_ESTIMATED = "Method: estimated";
export const METHOD_TAG_MEASURED = "Method: ref. measurement";

export const API_ERROR_HELP = [
  "python -m backend.batris.build_dataset",
  "python -m backend.batris.train_soh",
  "python -m backend.batris.train_tiers",
  "python -m backend.batris.train_anomaly",
] as const;

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

export const NAV_LINKS = [
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#capabilities", label: "Capabilities" },
  { href: "/#accuracy", label: "Accuracy" },
  { href: "/#passport", label: "Passport" },
] as const;

export const FOOTER_SECTIONS = [
  {
    title: "Platform",
    links: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/dashboard?view=own", label: "Assess my battery" },
      { href: "/#accuracy", label: "Measured accuracy" },
      { href: "/#passport", label: "Signed passports" },
    ],
  },
  {
    title: "Method",
    links: [
      { href: "/#how-it-works", label: "How it works" },
      { href: "/#capabilities", label: "What it reports" },
      { href: "/#passport-trust", label: "From assessment to record" },
      { href: "https://batris-project.onrender.com/docs", label: "API reference" },
    ],
  },
] as const;

// ---------------------------------------------------------------------------
// Landing page content
// ---------------------------------------------------------------------------

export const HERO = {
  eyebrow: "Second-life battery assessment",
  headlineTop: "Know what a used",
  headlineBottom: "battery is worth",
  body: "A capacity test costs a day on a bench cycler. This platform estimates state of health from an ordinary charge cycle, tells you why the pack is degrading, checks it against its own safety limits, and issues a signed passport a buyer can verify.",
  primaryCta: { href: "/dashboard", label: "Open the dashboard" },
  secondaryCta: { href: "/dashboard?view=own", label: "Assess my battery" },
} as const;

export const HERO_STATS = [
  { value: "2.67", unit: "SOH pts", label: "Best measured error" },
  { value: "4", unit: "cells", label: "Leave-one-out validation" },
  { value: "6", unit: "numbers", label: "Minimum useful input" },
] as const;

export const CAPABILITIES = [
  {
    title: "State of health",
    body: "A capacity estimate with a calibrated 90% interval, drawn from how the charge divides between its constant-current and constant-voltage phases.",
    tag: "Estimated",
  },
  {
    title: "Degradation attribution",
    body: "Which mechanism is taking the capacity — lithium inventory loss, resistance growth, thermal stress — and the measured signals behind each claim.",
    tag: "Explained",
  },
  {
    title: "Safety envelope",
    body: "A risk score with named drivers, plus derated charge current, SOC window and temperature limits computed from the pack's own format specification.",
    tag: "Derived",
  },
  {
    title: "Anomaly detection",
    body: "Physical rule checks, statistical outlier detection and trajectory deviation, each reported separately so silence from a detector is distinguishable from a clean result.",
    tag: "Detected",
  },
  {
    title: "Second-life grade",
    body: "A reuse grade on the point estimate, with the grade marked ambiguous whenever the confidence interval straddles a boundary.",
    tag: "Graded",
  },
  {
    title: "Signed passport",
    body: "An Ed25519-signed document carrying the assessment, the model provenance and the method labels. Alter one field and verification fails.",
    tag: "Verifiable",
  },
] as const;

export const HOW_IT_WORKS = [
  {
    step: "Charge it",
    body: "Run one ordinary charge. Either log it as CSV, or read six numbers off the charger display when it finishes.",
  },
  {
    step: "Submit what you have",
    body: "There is no fixed input set. The platform picks the richest tier your data supports and uses the model trained for exactly that tier.",
  },
  {
    step: "Read the estimate",
    body: "Health, safety, anomalies and reuse grade, each with the accuracy measured for your tier — not a headline number borrowed from the best case.",
  },
  {
    step: "Issue the passport",
    body: "Sign the assessment into a portable document. A buyer verifies it against the issuer's public key without trusting you.",
  },
] as const;

export const ACCURACY_ROWS = [
  {
    tier: "Tier 1",
    name: "Telemetry + impedance",
    input: "Full charge curve plus EIS values",
    mae: "2.67",
    r2: "0.867",
    reliable: true,
  },
  {
    tier: "Tier 2",
    name: "Telemetry",
    input: "Full charge curve, no impedance",
    mae: "2.75",
    r2: "0.858",
    reliable: true,
  },
  {
    tier: "Tier 3",
    name: "Charge summary",
    input: "Six hand-typed numbers",
    mae: "2.86",
    r2: "0.845",
    reliable: true,
  },
  {
    tier: "Tier 4",
    name: "Minimal",
    input: "Charge phase split only",
    mae: "5.58",
    r2: "0.127",
    reliable: false,
  },
] as const;

export const ACCURACY_NOTE =
  "Mean absolute error in SOH percentage points, measured by leave-one-battery-out cross-validation on four NASA cells. Each tier has its own separately trained and separately validated model, so a missing input never becomes a silent null in a model that never saw one.";

// export const LIMITS = [
//   {
//     title: "Four cells is a small training set",
//     body: "Every accuracy figure on this page comes from four 18650 LCO cells. It is enough to validate the method honestly; it is not enough to claim a production-grade model.",
//   },
//   {
//     title: "Other chemistries are extrapolation",
//     body: "Submit an LFP or NMC pack and the estimate is flagged as out-of-distribution and its interval widened. That widening factor is engineering judgement, not a measured quantity.",
//   },
//   {
//     title: "Tier 4 is where it breaks",
//     body: "With only the charge phase split, R² falls to 0.13 and the worst cell misses by 13 SOH points. The platform still answers, marks it indicative-only, and refuses to issue a reuse grade.",
//   },
//   {
//     title: "An estimate is not a certificate",
//     body: "Nothing here replaces accredited testing before a warranted resale. The point is to decide which packs are worth testing at all.",
//   },
// ] as const;

export const PASSPORT_FLOW = [
  {
    title: "One record, not a collection of reports",
    body: "The passport brings the battery’s health estimate, confidence interval, safety findings, degradation signals and second-life assessment into a single machine-readable record.",
  },

  {
    title: "A passport that stays with the battery",
    body: "The record can be issued as JSON or PDF and linked to the physical battery through a QR code, so the same assessment can be retrieved as the battery moves between owners, operators and its next use.",
  },

  {
    title: "A record a buyer can verify",
    body: "The passport is signed with Ed25519 over a canonical representation of the payload. Change a health value, model reference or other signed field and verification fails.",
  },

  {
    title: "Evidence for the next decision",
    body: "The passport preserves the inputs, model provenance and assessment results behind the decision, giving the next owner more than a single health number to work with.",
  },
] as const;

export const PASSPORT_SECTION = {
  eyebrow: "Tamper-evident by construction",
  title: "A claim a buyer can check without trusting the seller",
  body: "The passport is a JSON document signed with an Ed25519 key. It carries the health estimate, the confidence interval, the model provenance hash and an explicit label saying the figure was estimated rather than measured. Change the SOH from 78% to 97% and the signature stops verifying — which you can demonstrate from the dashboard in one click.",
  bullets: [
    "Ed25519 detached signature over a canonical serialisation",
    "Method labels travel with the numbers, so an estimate can never be read as a test result",
    "Model version, training-data hash and validation method embedded in the payload",
    "Verify against a published key, or paste the document into any Ed25519 verifier",
    "A QR code provides instant access to the battery passport for quick verification and lifecycle tracking",
  ],
} as const;

export const CTA = {
  title: "Point it at a battery",
  body: "Four NASA cells are loaded and ready to assess. Or bring your own charge log and see what your level of information actually buys you.",
  primary: { href: "/dashboard", label: "Open the dashboard" },
  secondary: { href: "/dashboard?view=own", label: "Assess my battery" },
} as const;

export const DISCLAIMER =
  "Estimates are not certified test results. Binding reuse, warranty or disposal decisions require accredited testing.";
