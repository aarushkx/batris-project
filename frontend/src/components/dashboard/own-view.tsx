"use client";

import * as React from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  FileUp,
  Gauge,
  Info,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  AnomalyList,
  ChargingEnvelopeGrid,
  DegradationFactors,
  DetectorCoverage,
  Mono,
  Recommendations,
  RiskDrivers,
  UnavailableAnalyses,
} from "@/components/shared/analysis";
import {
  Caveat,
  KeyValue,
  KeyValueGrid,
  Note,
  SectionCard,
  SubHeading,
} from "@/components/shared/primitives";
import { HeadlineMetrics } from "@/components/dashboard/headline-metrics";
import { PassportPanel } from "@/components/dashboard/passport-panel";
import {
  assessOwnBattery,
  getModelInfo,
  getOnboardingSchema,
  issueOwnPassport,
  registerFormat,
} from "@/lib/api";
import {
  CHEMISTRIES,
  EXAMPLE_BATTERY_ID,
  EXAMPLE_QUESTIONNAIRE,
  FORM_FACTORS,
  INPUT_MODES,
  TELEMETRY_CSV_ALIASES,
  TELEMETRY_CSV_COLUMNS,
  type InputMode,
} from "@/lib/constants";
import { EM_DASH } from "@/lib/format";
import type {
  InputFieldSpec,
  ModelInfo,
  OnboardingSchema,
  UnseenAssessment,
} from "@/lib/types";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ field --- */

function DynamicField({
  spec,
  value,
  onChange,
}: {
  spec: InputFieldSpec;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={`q_${spec.key}`} className="items-baseline">
        <span>{spec.label}</span>
        {!spec.required ? (
          <span className="text-[11px] font-normal text-ink-soft">optional</span>
        ) : null}
      </Label>
      <div className="flex items-center gap-2">
        <Input
          id={`q_${spec.key}`}
          type={spec.kind === "text" ? "text" : "number"}
          step={spec.kind === "number" ? "any" : undefined}
          min={spec.min ?? undefined}
          max={spec.max ?? undefined}
          placeholder={spec.placeholder || undefined}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        {spec.unit ? (
          <span className="shrink-0 text-[12px] whitespace-nowrap text-ink-soft">
            {spec.unit}
          </span>
        ) : null}
      </div>
      {spec.help ? (
        <p className="text-[11.5px] leading-relaxed text-ink-soft">{spec.help}</p>
      ) : null}
    </div>
  );
}

function FieldGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{children}</div>
  );
}

/* ======================================================================= */

const EMPTY_CUSTOM = {
  display_name: "",
  chemistry: "NMC",
  form_factor: "cylindrical_pack",
  rated_capacity_ah: "",
  nominal_voltage_v: "",
  v_max: "",
  v_min: "",
};

export function OwnView() {
  const [schema, setSchema] = React.useState<OnboardingSchema | null>(null);
  const [modelInfo, setModelInfo] = React.useState<ModelInfo | null>(null);
  const [schemaError, setSchemaError] = React.useState<string | null>(null);

  const [formatKey, setFormatKey] = React.useState("");
  const [batteryId, setBatteryId] = React.useState("");
  const [mode, setMode] = React.useState<InputMode>("questionnaire");
  const [answers, setAnswers] = React.useState<Record<string, string>>({});

  const [csvText, setCsvText] = React.useState<string | null>(null);
  const [csvInfo, setCsvInfo] = React.useState<{ name: string; rows: number; header: string } | null>(null);
  const [telAmbient, setTelAmbient] = React.useState("");
  const [telRe, setTelRe] = React.useState("");
  const [telRct, setTelRct] = React.useState("");

  const [custom, setCustom] = React.useState({ ...EMPTY_CUSTOM });
  const [customResult, setCustomResult] = React.useState<
    { ok: true; key: string; note?: string } | { ok: false; message: string } | null
  >(null);
  const [registering, setRegistering] = React.useState(false);

  const [assessment, setAssessment] = React.useState<UnseenAssessment | null>(null);
  const [assessing, setAssessing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const resultsRef = React.useRef<HTMLDivElement | null>(null);

  // ------------------------------------------------------------ bootstrap
  const loadSchema = React.useCallback(async (selectKey?: string) => {
    const next = await getOnboardingSchema();
    setSchema(next);
    setFormatKey((current) => selectKey ?? current ?? next.formats[0]?.key ?? "");
    return next;
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await getOnboardingSchema();
        if (cancelled) return;
        setSchema(next);
        setFormatKey(next.formats[0]?.key ?? "");
      } catch (err) {
        if (!cancelled) setSchemaError(err instanceof Error ? err.message : String(err));
      }
      try {
        const info = await getModelInfo();
        if (!cancelled) setModelInfo(info);
      } catch {
        /* Accuracies fall back to an em dash if the endpoint is unavailable. */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const manualTier = schema?.tiers.find((t) => t.key === schema.manual_tier);
  const questionFields = (manualTier?.fields ?? []).filter((f) => f.key !== "format_key");
  const contextFields = (schema?.context_fields ?? []).filter((f) => f.key !== "battery_id");
  const selectedFormat = schema?.formats.find((f) => f.key === formatKey);

  // ------------------------------------------------------------- payload
  const buildPayload = React.useCallback((): Record<string, unknown> => {
    const payload: Record<string, unknown> = {
      mode,
      format_key: formatKey,
      battery_id: batteryId || null,
    };

    if (mode === "telemetry") {
      payload.csv = csvText;
      if (telAmbient) payload.ambient_temp_c = Number(telAmbient);
      if (telRe) payload.re_ohm = Number(telRe);
      if (telRct) payload.rct_ohm = Number(telRct);
    } else {
      [...questionFields, ...contextFields].forEach((f) => {
        const value = answers[f.key];
        if (value !== undefined && value !== "") payload[f.key] = value;
      });
    }
    return payload;
  }, [
    mode,
    formatKey,
    batteryId,
    csvText,
    telAmbient,
    telRe,
    telRct,
    answers,
    questionFields,
    contextFields,
  ]);

  // -------------------------------------------------------------- assess
  async function handleAssess() {
    setAssessing(true);
    setError(null);
    try {
      if (mode === "telemetry" && !csvText) {
        throw new Error("Select a CSV file containing one charge cycle.");
      }
      const result = await assessOwnBattery(buildPayload());
      setAssessment(result);
      window.requestAnimationFrame(() =>
        resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAssessing(false);
    }
  }

  const issue = React.useCallback(
    () => issueOwnPassport(buildPayload()),
    [buildPayload],
  );

  function fillExample() {
    setAnswers((current) => {
      const next = { ...current };
      Object.entries(EXAMPLE_QUESTIONNAIRE).forEach(([key, value]) => {
        next[key] = String(value);
      });
      return next;
    });
    setBatteryId(EXAMPLE_BATTERY_ID);
    setMode("questionnaire");
  }

  async function handleCsv(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    const lines = text.trim().split("\n");
    setCsvText(text);
    setCsvInfo({
      name: file.name,
      rows: Math.max(0, lines.length - 1),
      header: lines[0]?.slice(0, 110) ?? "",
    });
  }

  async function handleRegisterFormat() {
    setRegistering(true);
    setCustomResult(null);
    try {
      const result = await registerFormat(custom);
      await loadSchema(result.format.key);
      setFormatKey(result.format.key);
      setCustomResult({
        ok: true,
        key: result.format.key,
        note: result.in_training_distribution
          ? undefined
          : `${result.format.chemistry} is outside the training data, so estimates will be flagged as extrapolation.`,
      });
    } catch (err) {
      setCustomResult({
        ok: false,
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setRegistering(false);
    }
  }

  // -------------------------------------------------------------- render
  if (schemaError) {
    return (
      <Alert variant="bad">
        <AlertTriangle />
        <AlertTitle>The onboarding schema could not be loaded.</AlertTitle>
        <AlertDescription>{schemaError}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="grid gap-3">
      {/* --------------------------------------------------- tier table */}
      <SectionCard
        title="Assess a battery that isn't in the dataset"
        description="Tell the platform what you know about your battery. There is no single required input set — the more you can supply, the more accurate the estimate, and the accuracy quoted to you is the figure measured for your level of information by leave-one-battery-out validation, not a headline number borrowed from the best case."
      >
        <TierTable
          schema={schema}
          modelInfo={modelInfo}
          currentTier={assessment?.input_tier.key}
        />
        <p className="mt-3 text-[12px] leading-relaxed text-ink-soft">
          Errors are mean absolute error in SOH percentage points, measured by
          leave-one-battery-out cross-validation on the NASA cells. Each tier has its own
          separately trained and separately validated model.
        </p>
      </SectionCard>

      {/* ------------------------------------------------ 1. what is it */}
      <SectionCard title="1. What is your battery?">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="ownFormat">Battery format</Label>
            <Select value={formatKey} onValueChange={setFormatKey}>
              <SelectTrigger id="ownFormat">
                <SelectValue placeholder={"Loading formats…"} />
              </SelectTrigger>
              <SelectContent>
                {(schema?.formats ?? []).map((f) => (
                  <SelectItem key={f.key} value={f.key}>
                    {f.display_name} — {f.rated_capacity_ah} Ah {f.chemistry}
                    {f.in_training_distribution ? "" : " (outside training data)"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedFormat ? (
              selectedFormat.in_training_distribution ? (
                <p className="text-[11.5px] leading-relaxed text-ink-soft">
                  Within the validated distribution (models trained on{" "}
                  {(schema?.trained_chemistries ?? []).join(", ")} cells).
                </p>
              ) : (
                <p className="text-[11.5px] leading-relaxed text-ink-soft">
                  <span className="font-semibold text-warn">
                    {selectedFormat.chemistry} is outside the training data.
                  </span>{" "}
                  The estimate will be flagged as extrapolation and its interval widened.
                </p>
              )
            ) : null}
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="ownBatteryId" className="items-baseline">
              <span>Identifier or serial</span>
              <span className="text-[11px] font-normal text-ink-soft">optional</span>
            </Label>
            <Input
              id="ownBatteryId"
              value={batteryId}
              placeholder="PACK-001"
              onChange={(e) => setBatteryId(e.target.value)}
            />
            <p className="text-[11.5px] text-ink-soft">Used to label the passport.</p>
          </div>
        </div>

        {/* --------------------------------------- custom format register */}
        <Collapsible className="mt-5 rounded-lg border border-line bg-mist/50 p-4">
          <CollapsibleTrigger className="group flex w-full cursor-pointer items-center justify-between gap-3 text-left text-[13px] font-medium">
            My battery format isn&apos;t listed — register it
            <ChevronDown className="size-4 shrink-0 text-ink-soft transition-transform group-data-[state=open]:rotate-180" />
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-4">
            <Note>
              Only the figures printed on a battery label are required. Anything you leave
              blank falls back to a conservative default, so an incompletely specified
              format produces <em>stricter</em> safety limits, never looser ones.
            </Note>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="cfName">Name</Label>
                <Input
                  id="cfName"
                  placeholder="My scooter pack 20 Ah"
                  value={custom.display_name}
                  onChange={(e) => setCustom({ ...custom, display_name: e.target.value })}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="cfChem">Chemistry</Label>
                <Select
                  value={custom.chemistry}
                  onValueChange={(v) => setCustom({ ...custom, chemistry: v })}
                >
                  <SelectTrigger id="cfChem">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CHEMISTRIES.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c === "OTHER" ? "Other" : c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="cfForm">Form factor</Label>
                <Select
                  value={custom.form_factor}
                  onValueChange={(v) => setCustom({ ...custom, form_factor: v })}
                >
                  <SelectTrigger id="cfForm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FORM_FACTORS.map((f) => (
                      <SelectItem key={f.value} value={f.value}>
                        {f.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {(
                [
                  ["rated_capacity_ah", "Rated capacity (Ah)", "20"],
                  ["nominal_voltage_v", "Nominal voltage (V)", "48"],
                  ["v_max", "Full-charge voltage (V)", "54.6"],
                  ["v_min", "Cutoff voltage (V)", "39"],
                ] as const
              ).map(([key, label, placeholder]) => (
                <div key={key} className="grid gap-1.5">
                  <Label htmlFor={`cf_${key}`}>{label}</Label>
                  <Input
                    id={`cf_${key}`}
                    type="number"
                    step="any"
                    placeholder={placeholder}
                    value={custom[key]}
                    onChange={(e) => setCustom({ ...custom, [key]: e.target.value })}
                  />
                </div>
              ))}
            </div>
            <Button className="mt-4" onClick={handleRegisterFormat} disabled={registering}>
              {registering ? <RefreshCw className="animate-spin" /> : <Check />}
              Register format
            </Button>
            {customResult ? (
              <div className="mt-3">
                {customResult.ok ? (
                  <Alert variant="good">
                    <Check />
                    <AlertTitle>
                      Registered <Mono>{customResult.key}</Mono> and selected it above.
                    </AlertTitle>
                    {customResult.note ? (
                      <AlertDescription>{customResult.note}</AlertDescription>
                    ) : null}
                  </Alert>
                ) : (
                  <Alert variant="bad">
                    <AlertTriangle />
                    <AlertTitle>{customResult.message}</AlertTitle>
                  </Alert>
                )}
              </div>
            ) : null}
          </CollapsibleContent>
        </Collapsible>
      </SectionCard>

      {/* --------------------------------------- 2. what info do you have */}
      <SectionCard title="2. What information do you have?">
        <div className="grid gap-2.5 sm:grid-cols-2">
          {INPUT_MODES.map((m) => {
            const active = mode === m.value;
            return (
              <button
                key={m.value}
                type="button"
                onClick={() => setMode(m.value)}
                aria-pressed={active}
                className={cn(
                  "cursor-pointer rounded-lg border p-4 text-left transition-colors",
                  active
                    ? "border-ink bg-ink text-white"
                    : "border-line bg-mist/50 hover:border-ink/25",
                )}
              >
                <div className="text-[13.5px] font-medium">{m.title}</div>
                <div
                  className={cn(
                    "mt-1 text-[11.5px]",
                    active ? "text-white/65" : "text-ink-soft",
                  )}
                >
                  {m.detail}
                </div>
              </button>
            );
          })}
        </div>

        {mode === "questionnaire" ? (
          <div className="mt-6">
            <FieldGrid>
              {questionFields.map((f) => (
                <DynamicField
                  key={f.key}
                  spec={f}
                  value={answers[f.key] ?? ""}
                  onChange={(v) => setAnswers((a) => ({ ...a, [f.key]: v }))}
                />
              ))}
            </FieldGrid>

            <SubHeading>Optional context</SubHeading>
            <Note>
              None of these change the estimate. The model reads your battery&apos;s
              present physical condition, not its paperwork — which is the point, since a
              used pack&apos;s history is usually unknown or untrustworthy. They inform the
              safety checks and appear on the passport.
            </Note>
            <div className="mt-4">
              <FieldGrid>
                {contextFields.map((f) => (
                  <DynamicField
                    key={f.key}
                    spec={f}
                    value={answers[f.key] ?? ""}
                    onChange={(v) => setAnswers((a) => ({ ...a, [f.key]: v }))}
                  />
                ))}
              </FieldGrid>
            </div>
          </div>
        ) : (
          <div className="mt-6">
            <Note>
              Upload a CSV covering <strong className="text-ink">one charge cycle</strong>,
              with columns{" "}
              {TELEMETRY_CSV_COLUMNS.map((c, i) => (
                <React.Fragment key={c}>
                  {i > 0 ? ", " : ""}
                  <Mono>{c}</Mono>
                </React.Fragment>
              ))}
              . Common alternative header names (
              {TELEMETRY_CSV_ALIASES.map((c, i) => (
                <React.Fragment key={c}>
                  {i > 0 ? ", " : ""}
                  <Mono>{c}</Mono>
                </React.Fragment>
              ))}
              ) are accepted. Charging current may be positive or negative; the sign
              convention is detected and normalised.
            </Note>

            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="grid gap-1.5">
                <Label htmlFor="csvFile">Charge log CSV</Label>
                <Input
                  id="csvFile"
                  type="file"
                  accept=".csv,text/csv"
                  onChange={handleCsv}
                  className="py-1.5"
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="telAmbient" className="items-baseline">
                  <span>Ambient temperature</span>
                  <span className="text-[11px] font-normal text-ink-soft">optional</span>
                </Label>
                <Input
                  id="telAmbient"
                  type="number"
                  step="any"
                  placeholder="25"
                  value={telAmbient}
                  onChange={(e) => setTelAmbient(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="telRe" className="items-baseline">
                  <span>Impedance Re (ohm)</span>
                  <span className="text-[11px] font-normal text-ink-soft">optional</span>
                </Label>
                <Input
                  id="telRe"
                  type="number"
                  step="any"
                  value={telRe}
                  onChange={(e) => setTelRe(e.target.value)}
                />
                <p className="text-[11.5px] text-ink-soft">
                  Only if you have EIS equipment. Unlocks tier 1.
                </p>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="telRct" className="items-baseline">
                  <span>Impedance Rct (ohm)</span>
                  <span className="text-[11px] font-normal text-ink-soft">optional</span>
                </Label>
                <Input
                  id="telRct"
                  type="number"
                  step="any"
                  value={telRct}
                  onChange={(e) => setTelRct(e.target.value)}
                />
              </div>
            </div>

            {csvInfo ? (
              <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-line bg-mist/60 px-3.5 py-2.5 text-[12px] text-ink-soft">
                <FileUp className="size-3.5" />
                Loaded <strong className="text-ink">{csvInfo.name}</strong> — {csvInfo.rows}{" "}
                rows. Header: <Mono>{csvInfo.header}</Mono>
              </div>
            ) : null}
          </div>
        )}

        <div className="mt-6 flex flex-wrap gap-2">
          <Button onClick={handleAssess} disabled={assessing}>
            {assessing ? <RefreshCw className="animate-spin" /> : <Gauge />}
            {assessing ? "Assessing\u2026" : "Assess my battery"}
          </Button>
          <Button variant="outline" onClick={fillExample}>
            <Sparkles />
            Fill with an example
          </Button>
        </div>

        {error ? (
          <div className="mt-4">
            <Alert variant="bad">
              <AlertTriangle />
              <AlertTitle>{error}</AlertTitle>
            </Alert>
          </div>
        ) : null}
      </SectionCard>

      {/* ------------------------------------------------------- results */}
      <div ref={resultsRef} className="scroll-mt-24">
        {assessment ? <OwnResults assessment={assessment} issue={issue} /> : null}
      </div>
    </div>
  );
}

/* ==================================================================== tiers */

function TierTable({
  schema,
  modelInfo,
  currentTier,
}: {
  schema: OnboardingSchema | null;
  modelInfo: ModelInfo | null;
  currentTier?: string;
}) {
  const maeByTier = React.useMemo(() => {
    const map = new Map<string, number | null>();
    (modelInfo?.tiers ?? []).forEach((t) => map.set(t.key, t.mae_soh_points));
    return map;
  }, [modelInfo]);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Level</TableHead>
          <TableHead>What you supply</TableHead>
          <TableHead className="text-right">Measured error</TableHead>
          <TableHead>Output</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {(schema?.tiers ?? []).map((t) => {
          const mae = maeByTier.get(t.key);
          const current = currentTier === t.key;
          return (
            <TableRow
              key={t.key}
              className={cn(
                current && "bg-estimated/6",
                !t.reliable && "text-ink-soft",
              )}
            >
              <TableCell className="whitespace-nowrap tabular font-medium">
                Tier {t.rank}
                {current ? (
                  <Badge variant="estimated" className="ml-2">
                    yours
                  </Badge>
                ) : null}
              </TableCell>
              <TableCell>
                <div className="font-medium">{t.display_name}</div>
                <div className="mt-0.5 text-[11.5px] leading-relaxed text-ink-soft">
                  {t.description}
                </div>
              </TableCell>
              <TableCell className="text-right whitespace-nowrap tabular">
                {mae != null ? `${mae.toFixed(2)} pts` : EM_DASH}
              </TableCell>
              <TableCell className="whitespace-nowrap">
                {t.reliable ? "Full report" : "Indicative only"}
              </TableCell>
            </TableRow>
          );
        })}
        {!schema
          ? [0, 1, 2, 3].map((i) => (
              <TableRow key={i}>
                <TableCell colSpan={4}>
                  <div className="h-6 animate-pulse rounded bg-mist" />
                </TableCell>
              </TableRow>
            ))
          : null}
      </TableBody>
    </Table>
  );
}

/* ================================================================== results */

function OwnResults({
  assessment: a,
  issue,
}: {
  assessment: UnseenAssessment;
  issue: () => Promise<import("@/lib/types").Passport>;
}) {
  const acc = a.input_tier.measured_accuracy ?? {};
  const detectorsRun = Object.values(a.anomaly.detectors_run ?? {}).filter(Boolean).length;

  return (
    <div className="grid gap-3">
      {/* --------------------------------------------- what input bought */}
      <SectionCard title="What your input supported">
        <KeyValueGrid>
          <KeyValue
            small
            label="Input level reached"
            value={`Tier ${a.input_tier.rank} — ${a.input_tier.display_name}`}
          />
          <KeyValue small label="Signals used" value={a.input_tier.n_features} />
          <KeyValue
            small
            label="Measured error at this tier"
            value={
              acc.mae_soh_percentage_points != null
                ? `${acc.mae_soh_percentage_points} SOH points (R\u00b2 ${acc.r2})`
                : EM_DASH
            }
          />
          <KeyValue
            small
            label="Worst case in validation"
            value={
              acc.worst_battery_mae_soh_points != null
                ? `${acc.worst_battery_mae_soh_points} SOH points`
                : EM_DASH
            }
          />
        </KeyValueGrid>

        <div className="mt-4 grid gap-3">
          {a.assumptions?.length ? (
            <Alert variant="info">
              <Info />
              <AlertTitle>Assumptions made from your input</AlertTitle>
              <AlertDescription>
                <ul className="list-disc space-y-1 pl-4">
                  {a.assumptions.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          ) : (
            <Alert variant="good">
              <Check />
              <AlertTitle>
                Every figure used came from your input directly; nothing had to be assumed.
              </AlertTitle>
            </Alert>
          )}

          {!a.chemistry_transfer.in_distribution ? (
            <Alert variant="warn">
              <AlertTriangle />
              <AlertTitle>
                Extrapolation warning — {a.chemistry_transfer.requested_chemistry} is
                outside the training data
              </AlertTitle>
              <AlertDescription>{a.chemistry_transfer.note}</AlertDescription>
            </Alert>
          ) : null}
        </div>
      </SectionCard>

      <HeadlineMetrics
        health={a.health}
        safety={a.safety}
        anomaly={a.anomaly}
        secondLife={a.second_life}
        eolThreshold={a.health.eol_threshold}
        anomalySub={`${detectorsRun} of 3 detectors could run`}
      />

      {/* --------------------------------------------------- unavailable */}
      <SectionCard
        title="What could not be assessed"
        description={
          "These analyses need information a single snapshot cannot provide. They are listed rather than silently omitted, because \u201cnothing found\u201d and \u201cnothing looked\u201d are different results."
        }
      >
        <UnavailableAnalyses items={a.unavailable_analyses} />
      </SectionCard>

      {/* ------------------------------------------------------- factors */}
      <SectionCard
        title="Why is this battery degrading?"
        description={a.degradation_summary}
      >
        <DegradationFactors factors={a.degradation_factors} />
        <Caveat>{a.explanation_caveat}</Caveat>
      </SectionCard>

      {/* ------------------------------------------------ safety + recs */}
      <div className="grid gap-3 lg:grid-cols-2">
        <SectionCard title="Safety assessment">
          <SubHeading>Risk drivers</SubHeading>
          <RiskDrivers drivers={a.safety.risk_drivers} />
          <SubHeading>Safe charging envelope</SubHeading>
          <ChargingEnvelopeGrid envelope={a.safety.safe_charging_envelope} />
        </SectionCard>
        <SectionCard title="Recommended practice">
          <Recommendations items={a.safety.recommendations} />
        </SectionCard>
      </div>

      {/* ----------------------------------------------------- anomalies */}
      <SectionCard title="Anomaly detections">
        <AnomalyList
          anomaly={a.anomaly}
          emptyNote="No anomalies detected. Normal capacity fade is expected behaviour and is not flagged as an anomaly."
        />
        <DetectorCoverage detectors={a.anomaly.detectors_run} />
        <Caveat>{a.anomaly.coverage_note}</Caveat>
      </SectionCard>

      {/* ------------------------------------------------------ passport */}
      <PassportPanel nextStep={a.second_life.next_step} issue={issue} />

      {/* ---------------------------------------------------- provenance */}
      <SectionCard
        title="Model provenance"
        description="Everything needed to reproduce or audit the number above."
      >
        <KeyValueGrid>
          <KeyValue small label="SOH model variant" value={a.model_provenance.soh_model_variant} />
          <KeyValue small label="Features used" value={a.model_provenance.soh_features_used} />
          <KeyValue small label="Validation method" value={a.model_provenance.validation_method} />
          <KeyValue
            small
            label="Out-of-sample MAE"
            value={
              a.model_provenance.validation_mae_soh_points != null
                ? `${a.model_provenance.validation_mae_soh_points} SOH pts`
                : EM_DASH
            }
          />
          <KeyValue
            small
            label="Training chemistries"
            value={(a.model_provenance.training_chemistries ?? []).join(", ") || EM_DASH}
          />
          <KeyValue small label="Training cycles" value={a.model_provenance.training_cycles ?? EM_DASH} />
          <KeyValue
            small
            label="Interval calibration"
            value={`${a.model_provenance.interval_calibration_factor}\u00d7`}
          />
          <KeyValue
            small
            label="Training data hash"
            value={a.model_provenance.training_data_sha256 ?? EM_DASH}
          />
        </KeyValueGrid>
      </SectionCard>
    </div>
  );
}
