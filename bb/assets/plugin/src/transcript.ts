import type { ThreadDelta, DeltaItemShape } from "@get-bb/plugin-sdk/provider-bridge";

export interface Block { type: string; text?: string; thinking?: string; id?: string; tool_call_id?: string; name?: string; input?: unknown; content?: string; is_error?: boolean; structured?: unknown }
export interface Message { id: string; role: string; status: string; blocks: Block[]; user_prompt?: { text?: string } }
export interface Frame {
  schema_version: string;
  operation?: string;
  structured_messages: Message[];
  history: { transcript_stream_id: string; generation: { id: string }; cursor: { resume_token: string }; tail_state: { activity: string; open_tool_call_ids?: string[]; pending_interaction_ids?: string[]; degraded?: boolean } };
}
const presentation = (label: string) => ({ label: { pending: label, completed: label }, icon: { glyph: "Bot" } });

export class Transcript {
  private messages = new Map<string, string>();
  private text = new Map<string, { text: string; closed: boolean }>();
  private tools = new Map<string, { name: string; input: unknown; closed: boolean }>();
  private base = new Set<string>();
  private stream = "";
  hasAssistant = false;
  pending = false;
  idle = false;
  constructor(snapshot: Frame, private bootstrapPrompt?: string) {
    this.assertFrame(snapshot, !!bootstrapPrompt);
    if (bootstrapPrompt) return;
    this.stream = snapshot.history.transcript_stream_id;
    for (const m of snapshot.structured_messages) this.base.add(m.id);
  }
  get waitingForPrompt() { return this.bootstrapPrompt !== undefined; }
  private assertFrame(frame: Frame, allowMissingHistory = false) {
    if (frame.schema_version !== "session.structured.v1" || !frame.history || !Array.isArray(frame.structured_messages)) throw new Error("Gas City did not return its 1.4 structured transcript contract");
    if (frame.history.tail_state.degraded && !allowMissingHistory) throw new Error("Gas City has no reliable structured transcript for this runtime; inspect the session in Gas City before retrying.");
  }
  apply(frame: Frame): ThreadDelta[] {
    this.assertFrame(frame, this.waitingForPrompt);
    if (this.bootstrapPrompt) {
      // Fresh GC sessions may expose only terminal fallback until first input.
      // Render nothing until normalized history contains our submitted prompt.
      if (frame.history.tail_state.degraded) return [];
      const first = frame.structured_messages.findIndex(message => message.role === "user" &&
        (message.user_prompt?.text ?? message.blocks.filter(b => b.type === "text").map(b => b.text ?? "").join("\n")).includes(this.bootstrapPrompt!));
      if (first === -1) {
        for (const message of frame.structured_messages) this.base.add(message.id);
        return [];
      }
      for (const message of frame.structured_messages.slice(0, first + 1)) this.base.add(message.id);
      this.bootstrapPrompt = undefined;
    }
    if (this.stream && frame.history.transcript_stream_id !== this.stream) throw new Error("Gas City changed transcript streams during this turn; inspect the session before continuing.");
    this.stream = frame.history.transcript_stream_id;
    if (frame.operation === "reset" && this.messages.size) throw new Error("Gas City rewrote the transcript during this turn. The bridge stopped replay to avoid duplicate or misleading history.");
    const deltas: ThreadDelta[] = [];
    const tail = frame.history.tail_state;
    this.idle = tail.activity === "idle";
    this.pending = !!tail.open_tool_call_ids?.length || !!tail.pending_interaction_ids?.length;
    for (const message of frame.structured_messages) {
      if (this.base.has(message.id)) continue;
      if (message.status === "superseded") throw new Error("Gas City superseded an entry in the active turn; inspect its current transcript.");
      const signature = JSON.stringify(message);
      if (this.messages.get(message.id) === signature) continue;
      this.messages.set(message.id, signature);
      if (message.role === "assistant") this.hasAssistant = true;
      for (const [index, block] of message.blocks.entries()) {
        const id = `gc-${message.id}-${block.id ?? index}`;
        const key = { providerItemId: id };
        if (message.role === "assistant" && (block.type === "text" || block.type === "thinking")) {
          const value = block.type === "text" ? block.text ?? "" : block.thinking ?? "";
          const old = this.text.get(id);
          if (old?.closed && old.text !== value) throw new Error("Gas City changed a completed message; inspect the remote transcript.");
          if (old && !value.startsWith(old.text)) throw new Error("Gas City rewrote streaming text; inspect the remote transcript.");
          const channel = block.type === "text" ? "agentMessage" : "reasoningText";
          if (!old) deltas.push({ kind: "item.open", key, item: block.type === "text" ? { type: "agentMessage", text: "" } : { type: "reasoning", summary: [], content: [] }, presentation: presentation(block.type === "text" ? "Gas City" : "Reasoning") });
          if (value.length > (old?.text.length ?? 0)) deltas.push({ kind: "item.textDelta", key, channel, text: value.slice(old?.text.length ?? 0) });
          const closed = message.status === "final";
          if (closed && !old?.closed) deltas.push({ kind: "item.textClose", key, channel, text: value });
          this.text.set(id, { text: value, closed });
        }
        if (block.type === "tool_use") {
          const callId = block.id ?? id;
          if (!this.tools.has(callId)) {
            this.tools.set(callId, { name: block.name ?? "Gas City tool", input: block.input, closed: false });
            deltas.push({ kind: "item.open", key: { providerItemId: `gc-tool-${callId}` }, item: { type: "tool", tool: block.name ?? "Gas City tool", args: block.input }, presentation: presentation(block.name ?? "Gas City tool") });
          }
        }
        if (block.type === "tool_result") {
          const callId = block.tool_call_id ?? block.id ?? id;
          const tool = this.tools.get(callId) ?? { name: "Gas City tool", input: undefined, closed: false };
          if (!tool.closed) {
            const item: DeltaItemShape = { type: "tool", tool: tool.name, args: tool.input, result: block.structured ?? block.content, ...(block.is_error ? { error: block.content ?? "Tool failed" } : {}) };
            deltas.push({ kind: "item.close", key: { providerItemId: `gc-tool-${callId}` }, item, status: block.is_error ? "failed" : "completed", presentation: presentation(tool.name) });
            this.tools.set(callId, { ...tool, closed: true });
          }
        }
      }
    }
    return deltas;
  }
  complete() { return this.hasAssistant && this.idle && !this.pending && [...this.text.values()].every(t => t.closed) && [...this.tools.values()].every(t => t.closed); }
}
