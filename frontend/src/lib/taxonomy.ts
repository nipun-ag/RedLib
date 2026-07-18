export const GATE_STORAGE_KEY = "redlib.researchGateAcknowledged"
export const CORPUS_FALLBACK_COUNT = 168_115

export type CorpusSource = {
  id: string
  label: string
  datasetId: string
  url: string
  host: string
}

/** Provenance list aligned with corpus/fetch_corpus.py SOURCE_REGISTRY. */
export const CORPUS_SOURCES: readonly CorpusSource[] = [
  {
    id: "harmbench",
    label: "HarmBench",
    datasetId: "swiss-ai/harmbench",
    url: "https://huggingface.co/datasets/swiss-ai/harmbench",
    host: "Hugging Face",
  },
  {
    id: "jackhhao",
    label: "Jailbreak Classification",
    datasetId: "jackhhao/jailbreak-classification",
    url: "https://huggingface.co/datasets/jackhhao/jailbreak-classification",
    host: "Hugging Face",
  },
  {
    id: "jailbreakbench_behaviors",
    label: "JailbreakBench Behaviors",
    datasetId: "JailbreakBench/JBB-Behaviors",
    url: "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors",
    host: "Hugging Face",
  },
  {
    id: "rubend18",
    label: "ChatGPT Jailbreak Prompts",
    datasetId: "rubend18/ChatGPT-Jailbreak-Prompts",
    url: "https://huggingface.co/datasets/rubend18/ChatGPT-Jailbreak-Prompts",
    host: "Hugging Face",
  },
  {
    id: "trustairlab",
    label: "In-the-Wild Jailbreak Prompts",
    datasetId: "TrustAIRLab/in-the-wild-jailbreak-prompts",
    url: "https://huggingface.co/datasets/TrustAIRLab/in-the-wild-jailbreak-prompts",
    host: "Hugging Face",
  },
  {
    id: "walledai",
    label: "MaliciousInstruct",
    datasetId: "walledai/MaliciousInstruct",
    url: "https://huggingface.co/datasets/walledai/MaliciousInstruct",
    host: "Hugging Face",
  },
  {
    id: "wildjailbreak",
    label: "WildJailbreak",
    datasetId: "allenai/wildjailbreak",
    url: "https://huggingface.co/datasets/allenai/wildjailbreak",
    host: "Hugging Face",
  },
] as const

export const SOURCE_NAMES = CORPUS_SOURCES.map((source) => source.id)

export const CATEGORY_FALLBACK_COUNTS: Record<string, number> = {
  "Role-Based Task Framing": 30876,
  "Fictional / Hypothetical Framing": 55707,
  "Authority or Legitimacy Spoofing": 4788,
  "Obfuscation / Encoding": 2225,
  "Simulation or Sandbox Framing": 34585,
  "Dual-Response or Comparative Framing": 2574,
  "Legitimate Context or Research Framing": 23310,
  "Contextual Reframing or Euphemism": 14050,
}

export const CATEGORY_NAMES = Object.keys(CATEGORY_FALLBACK_COUNTS)

/**
 * Short, authoritative display labels keyed by the canonical taxonomy name.
 *
 * The canonical name is the single source of truth: it is the value sent to
 * the API (`category_filter`, `/api/browse?category=`), what backend
 * validation accepts, and what is stored in Qdrant metadata / returned as
 * `technique`. These labels are presentation-only. To rename a display label,
 * edit the value here; never change the key. `categoryLabel()` falls back to
 * the canonical name for any unmapped category (e.g. a future backend
 * addition), so an unknown category still renders correctly.
 *
 * Label sources: OWASP secure-agent-playbook testing taxonomy, MITRE ATLAS
 * (AML.T0054), and the mechanism-oriented families in the 2025 "Guarding the
 * Guardrails" jailbreak taxonomy.
 */
export const CATEGORY_LABELS: Record<string, string> = {
  "Role-Based Task Framing": "Role Play",
  "Fictional / Hypothetical Framing": "Fictional Framing",
  "Authority or Legitimacy Spoofing": "Privilege Escalation",
  "Obfuscation / Encoding": "Obfuscation",
  "Simulation or Sandbox Framing": "Virtualization",
  "Dual-Response or Comparative Framing": "Dual Response",
  "Legitimate Context or Research Framing": "Benign Framing",
  "Contextual Reframing or Euphemism": "Disguised Intent",
}

/** Presentation label for a canonical taxonomy name; safe for any string. */
export function categoryLabel(canonicalName: string): string {
  return CATEGORY_LABELS[canonicalName] ?? canonicalName
}

export const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  "Role-Based Task Framing":
    "Prompts that instruct the model to adopt a specific persona, professional role, or fictional identity in order to bypass its default safety constraints.",
  "Fictional / Hypothetical Framing":
    "Prompts that embed harmful requests inside fictional scenarios, thought experiments, or hypothetical situations to make the model treat them as safe to answer.",
  "Authority or Legitimacy Spoofing":
    "Prompts that impersonate authoritative figures, institutions, or system-level instructions to convince the model it is operating under special permissions.",
  "Obfuscation / Encoding":
    "Prompts that disguise their true intent through encoding schemes, wordplay, structural manipulation, or indirect language to evade safety filters.",
  "Simulation or Sandbox Framing":
    "Prompts that convince the model it is operating inside a simulation, test environment, or sandboxed context where its normal safety rules do not apply.",
  "Dual-Response or Comparative Framing":
    "Prompts that ask the model to produce two contrasting responses simultaneously, typically one safe and one unrestricted, exploiting the comparative format to extract harmful content.",
  "Legitimate Context or Research Framing":
    "Prompts that justify harmful requests by presenting them as necessary for academic research, journalism, security testing, or other socially sanctioned purposes.",
  "Contextual Reframing or Euphemism":
    "Prompts that reframe harmful requests using softer language, euphemisms, or shifted context to make the model treat dangerous content as acceptable.",
}

export function formatNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—"
  }

  return new Intl.NumberFormat("en-US").format(value)
}

export function isGateAcknowledged(): boolean {
  return window.localStorage.getItem(GATE_STORAGE_KEY) === "true"
}

export function acknowledgeGate(): void {
  window.localStorage.setItem(GATE_STORAGE_KEY, "true")
}
