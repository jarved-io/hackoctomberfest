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

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

// Raw backend JSON is untyped by nature; it is normalized immediately below.
type Raw = Record<string, unknown>;

const str = (v: unknown, d = ""): string => (typeof v === "string" ? v : d);
const num = (v: unknown): number | undefined => (typeof v === "number" ? v : undefined);
const arr = (v: unknown): Raw[] => (Array.isArray(v) ? (v as Raw[]) : []);

/** Map the backend payload to the frontend shape. Person 1: tweak field names here only. */
export function normalizeResponse(raw: Raw): VerificationResponse {
  const issues: VerificationIssue[] = arr(raw.issues).map((i, idx) => {
    const s = i.suggestion;
    const sug = s && typeof s === "object" ? (s as Raw) : undefined;
    return {
      id: str(i.id, `issue-${idx}`),
      severity: str(i.severity, "warning") as Severity,
      type: str(i.type, "other") as IssueType,
      symbol: str(i.symbol ?? i.function ?? i.name),
      argument: typeof i.argument === "string" ? i.argument : undefined,
      line: num(i.line),
      message: str(i.message ?? i.explanation),
      suggestion: typeof s === "string"
        ? { replacement: s }
        : sug
          ? { original: str(sug.original) || undefined, replacement: str(sug.replacement), description: str(sug.description) || undefined }
          : undefined,
      version: typeof i.version === "string" ? i.version : undefined,
      evidence: typeof i.evidence === "string" ? i.evidence : undefined,
    };
  });
  const verifiedItems = arr(raw.verifiedItems).map((v) => ({
    symbol: str(v.symbol), kind: str(v.kind, "api"), message: typeof v.message === "string" ? v.message : undefined, line: num(v.line),
  }));
  const status: OverallStatus =
    (raw.overallStatus as OverallStatus | undefined) ??
    (issues.length === 0 ? "all_valid" : issues.some((i) => i.severity === "critical") ? "critical" : "issues_found");
  const ex = raw.explanation ?? raw.gemma;
  const exObj = ex && typeof ex === "object" ? (ex as Raw) : undefined;
  const text = typeof ex === "string" ? ex : str(exObj?.text);
  const explanation = text
    ? { text, correctedCode: str(exObj?.correctedCode ?? raw.correctedCode) || undefined }
    : undefined;
  return {
    overallStatus: status,
    issues,
    verifiedItems,
    suggestions: arr(raw.suggestions) as unknown as VerificationResponse["suggestions"],
    checkedCount: num(raw.checkedCount) ?? issues.length + verifiedItems.length,
    explanation,
    aiAvailable: raw.aiAvailable !== false && !raw.aiError,
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
      .filter((l) => l.name && l.versions.length);
    return out.length ? out : FALLBACK_LIBRARIES;
  } catch {
    return FALLBACK_LIBRARIES;
  }
}
