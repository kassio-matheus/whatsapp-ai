/**
 * Token saver (frontend).
 *
 * Mirrors the backend token saver so the UI never ships an unnecessarily fat
 * prompt to the AI gateway. The backend applies the real, per-model budgets
 * before calling the LLM; this utility is a cheap first pass that normalizes
 * and caps the outgoing prompt and — when the frontend ever holds a history —
 * prunes it down to the most recent essentials.
 *
 * Rough heuristic: ~1 token per 4 characters. Used only to bound sizes, never
 * to bill.
 */

const CHARS_PER_TOKEN = 4

/** Context budget per known model (tokens). Mirrors the backend defaults. */
export const MODEL_TOKEN_BUDGETS: Record<string, number> = {
  "deepseek-v4-flash": 3000,
  "gpt-5.6-luna": 3500,
  "gemini-3.5-flash-lite": 3000,
  "llama-3.1-8b-instant": 2500,
}

export const DEFAULT_TOKEN_BUDGET = 3000
export const MAX_PROMPT_TOKENS = 1200
export const MAX_CONTEXT_TURNS = 12

export function estimateTokens(text: string | null | undefined): number {
  if (!text) {
    return 0
  }
  return Math.max(1, Math.round(text.length / CHARS_PER_TOKEN))
}

/** Token budget for a given model id, falling back to a conservative default. */
export function budgetForModel(model?: string | null): number {
  if (!model) {
    return DEFAULT_TOKEN_BUDGET
  }
  return MODEL_TOKEN_BUDGETS[model] ?? DEFAULT_TOKEN_BUDGET
}

function toChars(tokens: number): number {
  return Math.max(1, tokens * CHARS_PER_TOKEN)
}

/**
 * Normalize a prompt: strip filler whitespace and cap it to `maxTokens`
 * characters-worth of tokens, keeping the leading intent.
 */
export function compactPrompt(
  text: string | null | undefined,
  maxTokens: number = MAX_PROMPT_TOKENS
): string {
  const cleaned = (text ?? "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
  if (!cleaned) {
    return ""
  }
  const limit = toChars(maxTokens)
  if (cleaned.length <= limit) {
    return cleaned
  }
  return `${cleaned.slice(0, Math.max(1, limit - 3)).trimEnd()}...`
}

/**
 * Trim a message list (conversation history) down to the `maxTokens` budget,
 * keeping the most recent turns. Old turns are dropped first; the total is
 * rechecked so very long recent replies still fit.
 */
export function trimMessages<T extends { content?: unknown }>(
  messages: readonly T[],
  maxTokens?: number
): T[] {
  if (!messages?.length) {
    return []
  }
  const limit = toChars(maxTokens ?? budgetForModel())
  let kept = messages.slice(-MAX_CONTEXT_TURNS)
  while (
    kept.length > 1 &&
    estimateTokens(kept.map((m) => String(m.content ?? "")).join(" ")) * CHARS_PER_TOKEN >
      limit
  ) {
    kept = kept.slice(1)
  }
  return [...kept]
}