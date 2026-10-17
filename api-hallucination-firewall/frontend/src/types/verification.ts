// Central frontend types. Adapt `normalizeResponse` in lib/api.ts if the backend schema changes.
export type OverallStatus = "all_valid" | "issues_found" | "critical" | "inconclusive" | "error";
export type Severity = "critical" | "warning" | "info";
export type IssueType =
  | "invalid_function"
  | "invalid_argument"
  | "invalid_import"
  | "invalid_class"
  | "other";

export interface VerificationRequest {
  code: string;
  library: string;
  version: string;
}

export interface Suggestion {
  original?: string;
  replacement: string;
  description?: string;
}

export interface VerificationIssue {
  id: string;
  severity: Severity;
  type: IssueType;
  symbol: string;
  argument?: string;
  line?: number; // only shown when the backend provides it
  message: string;
  suggestion?: Suggestion;
  version?: string;
  evidence?: string;
}

export interface VerifiedItem {
  symbol: string;
  kind: string; // "function" | "class" | "module" | ...
  message?: string;
  line?: number;
}

export interface GemmaExplanation {
  text: string;
  correctedCode?: string;
}

export interface VerificationResponse {
  overallStatus: OverallStatus;
  issues: VerificationIssue[];
  verifiedItems: VerifiedItem[];
  suggestions: Suggestion[];
  checkedCount: number;
  explanation?: GemmaExplanation;
  /** false => deterministic results are valid but Gemma failed */
  aiAvailable: boolean;
}

export interface LibraryOption {
  name: string;
  versions: string[];
}

export type ApiErrorKind = "empty" | "invalid" | "unavailable";
