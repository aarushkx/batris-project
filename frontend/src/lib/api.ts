import { API_ROUTES, type SohVariant } from "@/lib/constants";
import type {
  Assessment,
  BatterySummary,
  MarketBrowseResult,
  MarketListing,
  MarketListingDetail,
  ModelInfo,
  OnboardingSchema,
  Passport,
  PassportPdf,
  RegisterFormatResult,
  Timeline,
  TimelinePdf,
  UnseenAssessment,
  VerifyResult,
  BenchmarkResults,
} from "@/lib/types";

/**
 * FastAPI returns errors as `{"error": "..."}`.
 * This extracts the error message instead of showing only the status code.
 */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError(
      "Could not reach the assessment server. Start it with `python -m backend.batris.api` and reload.",
      0,
    );
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    /* Some failure modes return an empty body; fall through to the status. */
  }

  if (!response.ok) {
    const detail =
      (body as { error?: string; detail?: string } | null)?.error ??
      (body as { detail?: string } | null)?.detail ??
      `Request failed with status ${response.status}`;
    throw new ApiError(detail, response.status);
  }

  return body as T;
}

function postJSON<T>(url: string, payload: unknown): Promise<T> {
  return request<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/**
 * The session lives in an httpOnly cookie, so anything the backend guards with
 * require_user() has to opt into sending credentials.
 */
function authedJSON<T>(url: string, method: string, payload?: unknown): Promise<T> {
  return request<T>(url, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
}

/** Fetch a generated PDF and save it locally under a readable filename. */
async function downloadPdf(pdfUrl: string, filename: string) {
  const response = await fetch(pdfUrl, { credentials: "include" });
  if (!response.ok) {
    throw new ApiError(
      `Could not download the PDF (${response.status}).`,
      response.status,
    );
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// --------------------------------------------------------------------------
// Fleet view
// --------------------------------------------------------------------------

export function getBatteries() {
  return request<BatterySummary[]>(API_ROUTES.batteries);
}

export function getModelInfo() {
  return request<ModelInfo>(API_ROUTES.modelInfo);
}

export function assessBattery(
  batteryId: string,
  variant: SohVariant,
  cycle?: number | null,
) {
  const params = new URLSearchParams({ variant });
  if (cycle != null && Number.isFinite(cycle)) params.set("cycle", String(cycle));
  return request<Assessment>(`${API_ROUTES.assess(batteryId)}?${params}`);
}

export function issuePassport(
  batteryId: string,
  variant: SohVariant,
  cycle?: number | null,
) {
  return postJSON<Passport>(API_ROUTES.passport(batteryId), {
    variant,
    cycle: cycle ?? null,
  });
}

export function verifyPassport(document: unknown) {
  return postJSON<VerifyResult>(API_ROUTES.verifyWithIssuerKey, document);
}

/**
 * Generates the passport PDF on the server and returns its URL.
 * The QR code needs a URL to open the PDF when scanned.
 */
export function issuePassportPdf(document: Passport) {
  return postJSON<PassportPdf>(API_ROUTES.passportPdf, document);
}

/**
 * Re-renders a stored passport and downloads the resulting PDF locally.
 * The passport itself is the source of truth, so this also works for passports
 * reopened later from the account page.
 */
export async function downloadPassportPdf(passportDocument: Passport, filename: string) {
  const result = await issuePassportPdf(passportDocument);
  await downloadPdf(result.pdf_url, filename);
}

// --------------------------------------------------------------------------
// "Assess my own battery"
// --------------------------------------------------------------------------

export function getOnboardingSchema() {
  return request<OnboardingSchema>(API_ROUTES.onboardingSchema);
}

export function assessOwnBattery(payload: Record<string, unknown>) {
  return postJSON<UnseenAssessment>(API_ROUTES.onboardingAssess, payload);
}

export function issueOwnPassport(payload: Record<string, unknown>) {
  return postJSON<Passport>(API_ROUTES.onboardingPassport, payload);
}

export function registerFormat(payload: Record<string, unknown>) {
  return postJSON<RegisterFormatResult>(API_ROUTES.onboardingFormat, payload);
}

// --------------------------------------------------------------------------
// Benchmark
// --------------------------------------------------------------------------

export function getBenchmarkResults() {
  return request<BenchmarkResults>(API_ROUTES.benchmark);
}

// --------------------------------------------------------------------------
// Health timeline
// --------------------------------------------------------------------------

/**
 * Builds a timeline from an assessment the client already holds, so switching
 * to the timeline never re-runs the model or risks a second, slightly
 * different SOH estimate appearing next to the first.
 */
export function buildTimeline(assessment: Assessment | UnseenAssessment) {
  return postJSON<Timeline>(API_ROUTES.timeline, { assessment });
}

/** Timeline for a dataset battery, assessed server-side. */
export function getBatteryTimeline(
  batteryId: string,
  variant: SohVariant,
  cycle?: number | null,
) {
  const params = new URLSearchParams({ variant });
  if (cycle != null && Number.isFinite(cycle)) params.set("cycle", String(cycle));
  return request<Timeline>(`${API_ROUTES.timelineFor(batteryId)}?${params}`);
}

export function issueTimelinePdf(timeline: Timeline) {
  return postJSON<TimelinePdf>(API_ROUTES.timelinePdf, { timeline });
}

/** Render the timeline to PDF on the server, then download it. */
export async function downloadTimelinePdf(timeline: Timeline, filename: string) {
  const result = await issueTimelinePdf(timeline);
  await downloadPdf(result.pdf_url, filename);
  return result;
}

// --------------------------------------------------------------------------
// Second-life market
// --------------------------------------------------------------------------

export function browseMarket(filters: {
  grade?: string | null;
  chemistry?: string | null;
  minSoh?: number | null;
}) {
  const params = new URLSearchParams();
  if (filters.grade && filters.grade !== "all") params.set("grade", filters.grade);
  if (filters.chemistry && filters.chemistry !== "all") {
    params.set("chemistry", filters.chemistry);
  }
  if (filters.minSoh != null && Number.isFinite(filters.minSoh)) {
    params.set("min_soh", String(filters.minSoh));
  }
  const query = params.toString();
  return request<MarketBrowseResult>(
    query ? `${API_ROUTES.marketListings}?${query}` : API_ROUTES.marketListings,
  );
}

export function getMarketListing(listingId: string) {
  return request<MarketListingDetail>(API_ROUTES.marketListing(listingId));
}

export function publishListing(payload: {
  assessment: Assessment | UnseenAssessment;
  title?: string | null;
  location?: string | null;
  notes?: string | null;
  passport?: Passport | null;
}) {
  return authedJSON<{ published: boolean; listing: MarketListing }>(
    API_ROUTES.marketListings,
    "POST",
    payload,
  );
}

export function getMyListings() {
  return authedJSON<{ items: MarketListing[] }>(API_ROUTES.marketMine, "GET");
}

export function withdrawListing(listingId: string) {
  return authedJSON<{ withdrawn: boolean; listing_id: string }>(
    API_ROUTES.marketListing(listingId),
    "DELETE",
  );
}
