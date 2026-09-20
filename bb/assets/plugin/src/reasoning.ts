export const REASONING_LEVELS = ["none", "low", "medium", "high", "xhigh", "max"] as const;
export type ReasoningLevel = typeof REASONING_LEVELS[number];
export const reasoningLabel = (level: ReasoningLevel) => ({ none: "Agent default", low: "Low", medium: "Medium", high: "High", xhigh: "Extra High", max: "Max" })[level];
export const reasoningDescription = (level: ReasoningLevel) => level === "none"
  ? "Use the Gas City agent's configured effort."
  : `Set Gas City effort to ${level} when creating this conversation.`;

export interface PublicProvider {
  name: string;
  options_schema?: { key: string; type: string; choices?: { value: string }[] }[];
}
export function providerReasoning(provider?: PublicProvider): ReasoningLevel[] {
  const effort = provider?.options_schema?.find(option => option.key === "effort" && option.type === "select");
  return REASONING_LEVELS.filter(level => level === "none" || effort?.choices?.some(choice => choice.value === level));
}
export function validateReasoning(level: unknown, allowed: readonly ReasoningLevel[]): ReasoningLevel {
  const selected = level ?? "none";
  if (!allowed.includes(selected as ReasoningLevel)) throw new Error(`This Gas City agent does not support reasoning level ${String(selected)}. Supported levels: ${allowed.map(reasoningLabel).join(", ")}. Refresh and choose again.`);
  return selected as ReasoningLevel;
}
export function requireSameReasoning(selected: unknown, original: ReasoningLevel = "none"): void {
  if ((selected ?? "none") !== original) throw new Error(`This Gas City conversation's reasoning is fixed at ${reasoningLabel(original)}. Select that level again or create a new BB thread to change it.`);
}
