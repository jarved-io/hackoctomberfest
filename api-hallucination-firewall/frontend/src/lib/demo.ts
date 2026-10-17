// TEMPORARY DEMO DATA. Used only for example buttons (code snippets) and when
// NEXT_PUBLIC_USE_MOCK=true. Never used as a silent fallback for real verification.
import type { LibraryOption, VerificationResponse } from "@/types/verification";

export const FALLBACK_LIBRARIES: LibraryOption[] = [{ name: "requests", versions: ["2.32.3", "2.31.0", "2.28.2", "2.25.1"] }];

export interface DemoExample {
  id: string;
  label: string;
  code: string;
  response: VerificationResponse;
}

const get = { symbol: "requests.get()", kind: "function", message: "Function exists" };

export const DEMO_EXAMPLES: DemoExample[] = [
  {
    id: "fake-function",
    label: "Fake function",
    code: `import requests\n\nresponse = requests.fetch(\n    "https://example.com"\n)`,
    response: {
      overallStatus: "critical",
      checkedCount: 2,
      aiAvailable: true,
      issues: [{
        id: "d1", severity: "critical", type: "invalid_function", symbol: "requests.fetch()", line: 3,
        message: "requests.fetch() does not exist in requests 2.31.0.",
        suggestion: { original: "requests.fetch", replacement: "requests.get", description: "Closest valid API" },
        version: "2.31.0", evidence: "Symbol not found in requests 2.31.0 public API surface.",
      }],
      verifiedItems: [{ symbol: "requests", kind: "module", message: "Module exists", line: 1 }],
      suggestions: [{ original: "requests.fetch", replacement: "requests.get" }],
      explanation: {
        text: "`requests.fetch()` is not part of the selected API version. The closest verified function is `requests.get()`.",
        correctedCode: `import requests\n\nresponse = requests.get(\n    "https://example.com"\n)`,
      },
    },
  },
  {
    id: "fake-argument",
    label: "Fake argument",
    code: `import requests\n\nresponse = requests.get(\n    "https://example.com",\n    timeout_seconds=10\n)`,
    response: {
      overallStatus: "issues_found",
      checkedCount: 3,
      aiAvailable: true,
      issues: [{
        id: "d2", severity: "warning", type: "invalid_argument", symbol: "requests.get()", argument: "timeout_seconds", line: 5,
        message: "requests.get() does not support this argument in version 2.31.0.",
        suggestion: { original: "timeout_seconds", replacement: "timeout", description: "Valid argument" },
        version: "2.31.0", evidence: "Signature: get(url, params=None, **kwargs); `timeout` is a documented kwarg.",
      }],
      verifiedItems: [{ symbol: "requests", kind: "module", line: 1, message: "Module exists" }, { ...get, line: 3 }],
      suggestions: [{ original: "timeout_seconds", replacement: "timeout" }],
      explanation: {
        text: "`requests.get()` exists in the selected API version, but `timeout_seconds` is not a supported argument. The verified API uses `timeout` instead.",
        correctedCode: `import requests\n\nresponse = requests.get(\n    "https://example.com",\n    timeout=10\n)`,
      },
    },
  },
  {
    id: "valid",
    label: "Valid code",
    code: `import requests\n\nresponse = requests.get(\n    "https://example.com",\n    timeout=10\n)`,
    response: {
      overallStatus: "all_valid",
      checkedCount: 3,
      aiAvailable: true,
      issues: [],
      verifiedItems: [{ symbol: "requests", kind: "module", line: 1, message: "Module exists" }, { ...get, line: 3 }, { symbol: "timeout", kind: "argument", line: 5, message: "Argument is valid" }],
      suggestions: [],
    },
  },
];
