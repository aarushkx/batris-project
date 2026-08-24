// import { API_ROUTES, type SohVariant } from "@/lib/constants";
// import type {
//   Assessment,
//   BatterySummary,
//   ModelInfo,
//   OnboardingSchema,
//   Passport,
//   PassportPdf,
//   RegisterFormatResult,
//   UnseenAssessment,
//   VerifyResult,
// } from "@/lib/types";

// /**
//  * FastAPI returns errors as `{"error": "..."}`.
//  * This extracts the error message instead of showing only the status code.
//  */
// export class ApiError extends Error {
//   status: number;
//   constructor(message: string, status: number) {
//     super(message);
//     this.name = "ApiError";
//     this.status = status;
//   }
// }

// async function request<T>(url: string, init?: RequestInit): Promise<T> {
//   let response: Response;
//   try {
//     response = await fetch(url, init);
//   } catch {
//     throw new ApiError(
//       "Could not reach the assessment server. Start it with `python -m backend.batris.api` and reload.",
//       0,
//     );
//   }

//   let body: unknown = null;
//   try {
//     body = await response.json();
//   } catch {
//     /* Some failure modes return an empty body; fall through to the status. */
//   }

//   if (!response.ok) {
//     const detail =
//       (body as { error?: string; detail?: string } | null)?.error ??
//       (body as { detail?: string } | null)?.detail ??
//       `Request failed with status ${response.status}`;
//     throw new ApiError(detail, response.status);
//   }

//   return body as T;
// }

// function postJSON<T>(url: string, payload: unknown): Promise<T> {
//   return request<T>(url, {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify(payload),
//   });
// }

// // --------------------------------------------------------------------------
// // Fleet view
// // --------------------------------------------------------------------------

// export function getBatteries() {
//   return request<BatterySummary[]>(API_ROUTES.batteries);
// }

// export function getModelInfo() {
//   return request<ModelInfo>(API_ROUTES.modelInfo);
// }

// export function assessBattery(
//   batteryId: string,
//   variant: SohVariant,
//   cycle?: number | null,
// ) {
//   const params = new URLSearchParams({ variant });
//   if (cycle != null && Number.isFinite(cycle)) params.set("cycle", String(cycle));
//   return request<Assessment>(`${API_ROUTES.assess(batteryId)}?${params}`);
// }

// export function issuePassport(
//   batteryId: string,
//   variant: SohVariant,
//   cycle?: number | null,
// ) {
//   return postJSON<Passport>(API_ROUTES.passport(batteryId), {
//     variant,
//     cycle: cycle ?? null,
//   });
// }

// export function verifyPassport(document: unknown) {
//   return postJSON<VerifyResult>(API_ROUTES.verifyWithIssuerKey, document);
// }

// /**
//  * Generates the passport PDF on the server and returns its URL.
//  * The QR code needs a URL to open the PDF when scanned.
//  */
// export function issuePassportPdf(document: Passport) {
//   return postJSON<PassportPdf>(API_ROUTES.passportPdf, document);
// }

// // --------------------------------------------------------------------------
// // "Assess my own battery"
// // --------------------------------------------------------------------------

// export function getOnboardingSchema() {
//   return request<OnboardingSchema>(API_ROUTES.onboardingSchema);
// }

// export function assessOwnBattery(payload: Record<string, unknown>) {
//   return postJSON<UnseenAssessment>(API_ROUTES.onboardingAssess, payload);
// }

// export function issueOwnPassport(payload: Record<string, unknown>) {
//   return postJSON<Passport>(API_ROUTES.onboardingPassport, payload);
// }

// export function registerFormat(payload: Record<string, unknown>) {
//   return postJSON<RegisterFormatResult>(API_ROUTES.onboardingFormat, payload);
// }

import { API_ROUTES, type SohVariant } from "@/lib/constants";
import type {
  Assessment,
  BatterySummary,
  ModelInfo,
  OnboardingSchema,
  Passport,
  PassportPdf,
  RegisterFormatResult,
  UnseenAssessment,
  VerifyResult,
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
  const response = await fetch(result.pdf_url, { credentials: "include" });
  if (!response.ok) {
    throw new ApiError(`Could not download the passport PDF (${response.status}).`, response.status);
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
