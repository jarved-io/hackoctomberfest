// The ONLY place the frontend talks to the backend.
import type {
  ApiErrorKind, LibraryOption, OverallStatus, Severity, IssueType,
  VerificationIssue, VerificationRequest, VerificationResponse,
} from "@/types/verification";
import { DEMO_EXAMPLES, FALLBACK_LIBRARIES } from "@/lib/demo";

export class ApiError extends Error {
  constructor(public kind: ApiErrorKind, message: string) { super(message); }
}

export const ERROR_MESSAGES: Record<ApiErrorKind, string> = {
  empty: "Please enter some code before verifying.",
  invalid: "We couldn't process this verification. Check your code and try again.",
  unavailable: "Verification service is currently unavailable. Please try again.",
};

function compareVersionsDesc(a: string, b: string): number {
  const pa = a.split(/[.\-]/).map((x) => parseInt(x, 10) || 0);
  const pb = b.split(/[.\-]/).map((x) => parseInt(x, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pb[i] ?? 0) - (pa[i] ?? 0);
    if (d !== 0) return d;
  }
  return 0;
}

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

// Raw backend JSON is untyped by nature; it is normalized immediately below.
type Raw = Record<string, unknown>;

const str = (v: unknown, d = ""): string => (typeof v === "string" ? v : d);
const num = (v: unknown): number | undefined => (typeof v === "number" ? v : undefined);
const arr = (v: unknown): Raw[] => (Array.isArray(v) ? (v as Raw[]) : []);

const SYMBOL_LEVEL = new Set(["invalid_symbol", "invalid_import", "unresolved_symbol", "invalid_function", "invalid_class"]);

const TYPE_MAP: Record<string, IssueType> = {
  invalid_symbol: "invalid_function",
  invalid_import: "invalid_import",
  invalid_keyword: "invalid_argument",
  invalid_argument: "invalid_argument",
  invalid_positional_argument: "invalid_argument",
  excessive_positional_arguments: "invalid_argument",
  invalid_function: "invalid_function",
  invalid_class: "invalid_class",
};

/** Backend severities are error|warning|info; the UI uses critical|warning|info. */
function mapSeverity(type: string, sev: string): Severity {
  if (sev === "critical") return "critical";
  if (sev === "error") return SYMBOL_LEVEL.has(type) || type === "syntax_error" ? "critical" : "warning";
  if (sev === "info") return "info";
  return "warning";
}

function evidenceText(e: unknown): string | undefined {
  if (typeof e === "string") return e;
  if (!e || typeof e !== "object") return undefined;
  const o = e as Raw;
  const parts: string[] = [];
  if (str(o.library) && str(o.version)) parts.push(`Checked against ${str(o.library)} ${str(o.version)}.`);
  if (Array.isArray(o.knownArguments) && o.knownArguments.length) parts.push(`Accepted arguments: ${(o.knownArguments as string[]).join(", ")}.`);
  if (str(o.referenceSource)) parts.push(`Source: ${str(o.referenceSource)}`);
  return parts.join(" ") || undefined;
}

/** Map the backend payload (POST /api/verify) to the frontend shape. */
export function normalizeResponse(raw: Raw): VerificationResponse {
  const topSuggestions = arr(raw.suggestions);
  const issues: VerificationIssue[] = arr(raw.issues).map((i, idx) => {
    const s = i.suggestion;
    const sug = s && typeof s === "object" ? (s as Raw) : undefined;
    const rawType = str(i.type, "other");
    const argument = typeof i.argument === "string" ? i.argument : undefined;
    const symbol = str(i.symbol ?? i.function ?? i.name);
    const line = num(i.line);
    // Backend sends suggestions as a top-level list; attach the best match to its issue.
    const match = topSuggestions.find(
      (t) => num(t.line) === line && str(t.symbol) === symbol && str(t.original) === (argument ?? symbol),
    );
    let suggestion: VerificationIssue["suggestion"];
    if (typeof s === "string") suggestion = { replacement: s };
    else if (sug) suggestion = { original: str(sug.original) || undefined, replacement: str(sug.replacement), description: str(sug.description) || undefined };
    else if (match) suggestion = { original: str(match.original) || undefined, replacement: str(match.suggested), description: str(match.reason) || undefined };
    return {
      id: str(i.id, `issue-${idx}`),
      severity: mapSeverity(rawType, str(i.severity, "warning")),
      type: TYPE_MAP[rawType] ?? "other",
      symbol,
      argument,
      line,
      message: str(i.message ?? i.explanation),
      suggestion,
      version: typeof i.version === "string" ? i.version : undefined,
      evidence: evidenceText(i.evidence),
    };
  });
  const verifiedItems = arr(raw.verifiedItems).map((v) => ({
    symbol: str(v.symbol),
    kind: str(v.kind, "api"),
    message: typeof v.message === "string" ? v.message : Array.isArray(v.checksPassed) && v.checksPassed.includes("symbol_exists") ? "Exists in the trusted API data" : undefined,
    line: num(v.line),
  }));

  const real = issues.filter((i) => i.severity !== "info");
  const rawStatus = raw.overallStatus as string | undefined;
  let status: OverallStatus;
  if (rawStatus === "passed" || rawStatus === "all_valid") status = "all_valid";
  else if (rawStatus === "inconclusive" || rawStatus === "error") status = rawStatus;
  else if (rawStatus === "critical") status = "critical";
  else if (rawStatus === "issues_found") status = real.some((i) => i.severity === "critical") ? "critical" : "issues_found";
  else status = real.length === 0 ? "all_valid" : real.some((i) => i.severity === "critical") ? "critical" : "issues_found";

  // Gemma explanation: backend field `ai` (see ai_module ExplanationResult); legacy `explanation`/`gemma` also accepted.
  const ai = raw.ai && typeof raw.ai === "object" ? (raw.ai as Raw) : undefined;
  const ex = raw.explanation ?? raw.gemma;
  const exObj = ex && typeof ex === "object" ? (ex as Raw) : undefined;
  let explanation: VerificationResponse["explanation"];
  let aiAvailable: boolean;
  if (ai) {
    aiAvailable = str(ai.aiStatus) === "ok";
    const body = [str(ai.summary), str(ai.explanation)].filter(Boolean).join("\n\n");
    const note = ai.correctionIsPartial ? "\n\nNote: the suggested correction fixes only the flagged line(s), not the whole program." : "";
    explanation = aiAvailable && body ? { text: body + note, correctedCode: str(ai.correctedSnippet) || undefined } : undefined;
  } else if (raw.ai === null && !ex) {
    aiAvailable = false; // backend ran without an explanation (disabled / nothing to explain)
  } else {
    const text = typeof ex === "string" ? ex : str(exObj?.text);
    explanation = text ? { text, correctedCode: str(exObj?.correctedCode ?? raw.correctedCode) || undefined } : undefined;
    aiAvailable = raw.aiAvailable !== false && !raw.aiError;
  }

  const symbolLevelIssues = arr(raw.issues).filter((i) => SYMBOL_LEVEL.has(str(i.type))).length;
  return {
    overallStatus: status,
    issues,
    verifiedItems,
    suggestions: topSuggestions.map((t) => ({ original: str(t.original) || undefined, replacement: str(t.suggested ?? t.replacement), description: str(t.reason ?? t.description) || undefined })),
    checkedCount: num(raw.checkedCount) ?? verifiedItems.length + symbolLevelIssues,
    explanation,
    aiAvailable,
  };
}

async function mockVerify(req: VerificationRequest): Promise<VerificationResponse> {
  await new Promise((r) => setTimeout(r, 700));
  const hit = DEMO_EXAMPLES.find((e) => e.code.trim() === req.code.trim());
  if (!hit) throw new ApiError("unavailable", ERROR_MESSAGES.unavailable);
  return hit.response;
}

export async function verifyCode(req: VerificationRequest): Promise<VerificationResponse> {
  if (!req.code.trim()) throw new ApiError("empty", ERROR_MESSAGES.empty);
  if (USE_MOCK) return mockVerify(req);
  let res: Response;
  try {
    res = await fetch("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
  } catch {
    throw new ApiError("unavailable", ERROR_MESSAGES.unavailable);
  }
  if (res.status === 400 || res.status === 422) throw new ApiError("invalid", ERROR_MESSAGES.invalid);
  if (!res.ok) throw new ApiError("unavailable", ERROR_MESSAGES.unavailable);
  try {
    return normalizeResponse((await res.json()) as Raw);
  } catch {
    throw new ApiError("invalid", ERROR_MESSAGES.invalid);
  }
}

/** Optional: GET /api/libraries -> [{ name, versions }]. Falls back to demo values. */
export async function getLibraries(): Promise<LibraryOption[]> {
  if (USE_MOCK) return FALLBACK_LIBRARIES;
  try {
    const res = await fetch("/api/libraries");
    if (!res.ok) return FALLBACK_LIBRARIES;
    const data = (await res.json()) as unknown;
    const list = Array.isArray(data) ? data : (data as Raw).libraries;
    const out = arr(list)
      .map((l) => ({ name: str(l.name), versions: Array.isArray(l.versions) ? (l.versions as string[]) : [] }))
      .filter((l) => l.name && l.versions.length)
      .map((l) => ({ ...l, versions: [...l.versions].sort(compareVersionsDesc) }));
    return out.length ? out : FALLBACK_LIBRARIES;
  } catch {
    return FALLBACK_LIBRARIES;
  }
}
