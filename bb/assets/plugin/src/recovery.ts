import { createHash } from "node:crypto";
import { ApiError, GasCityClient } from "./client.js";
import { Journal, type Receipt } from "./journal.js";
import { Transcript, type Frame } from "./transcript.js";
import type { Config } from "./config.js";

export const sessionAlias = (threadId: string) => `bb-${createHash("sha256").update(threadId).digest("hex").slice(0, 24)}`;

/** Resolve creation without repeating the mutation, including a lost HTTP reply. */
export async function resolveCreation(client: GasCityClient, threadId: string, receipt: Receipt): Promise<string> {
  if (receipt.sessionId) return receipt.sessionId;
  const alias = receipt.alias ?? sessionAlias(threadId);
  const remote = receipt.create
    ? (await client.result(receipt.target.city, receipt.create, "create")).session
    : await client.get(client.session(receipt.target.city, alias)).catch(error => {
      if (error instanceof ApiError && error.status === 404) throw new Error(`Creation of ${alias} remains uncertain. It has not appeared in Gas City; retry recovery after creation settles. No new session was created.`);
      throw error;
    });
  if (!remote?.id || remote.template !== receipt.target.agent || (remote.alias !== alias && !receipt.create))
    throw new Error(`Gas City session identity does not match the recorded creation of ${alias}`);
  return remote.id;
}

export async function recoverThread(config: Config, journal: Journal, threadId: string, options: { signal?: AbortSignal; requestId?: string; eventCursor?: string } = {}): Promise<Receipt> {
  if ((options.requestId === undefined) !== (options.eventCursor === undefined)) throw new Error("Supply both --request-id and --event-cursor from the original Gas City request.");
  return journal.locked(threadId, async () => {
    const receipt = await journal.get(threadId);
    if (!receipt) throw new Error("No ownership receipt exists for this BB thread");
    const connection = config.connections.find(c => c.id === receipt.target.connection);
    if (!connection) throw new Error("Restore this thread's original connection first");
    const client = new GasCityClient(connection);
    receipt.sessionId = await resolveCreation(client, threadId, receipt);
    if (receipt.turn && !["completed", "failed"].includes(receipt.turn.state)) {
      if (options.requestId !== undefined) {
        if (receipt.turn.request_id && receipt.turn.request_id !== options.requestId) throw new Error("The supplied request ID differs from the journaled request. Preserve the original receipt.");
        receipt.turn.request_id = options.requestId;
        receipt.turn.event_cursor = options.eventCursor;
      }
      if (!receipt.turn.request_id || receipt.turn.event_cursor === undefined) throw new Error("The submit response was lost, so delivery cannot be correlated. Preserve the receipt and inspect Gas City events; use recover --request-id <original-request-ID> --event-cursor <original-cursor> --confirm-reviewed. No prompt was resent.");
      const result = await client.result(receipt.target.city, { request_id: receipt.turn.request_id, event_cursor: receipt.turn.event_cursor }, "submit", options.signal);
      if (result.session_id !== receipt.sessionId) throw new Error("The recorded submit result belongs to a different Gas City session");
      const snapshot = await client.get(client.session(receipt.target.city, receipt.sessionId, "/transcript?format=structured"), options.signal);
      const pending = await client.get(client.session(receipt.target.city, receipt.sessionId, "/pending"), options.signal);
      if (snapshot.history?.tail_state?.activity !== "idle" || snapshot.history.tail_state.degraded || snapshot.history.tail_state.open_tool_call_ids?.length || snapshot.history.tail_state.pending_interaction_ids?.length || pending.pending) throw new Error("The remote session is still active, degraded, or awaiting a response");
      const messages = (snapshot as Frame).structured_messages;
      const turn = receipt.turn;
      if (!turn.baselineMessageIds || !turn.messageDigest) throw new Error("This older receipt lacks prompt history evidence. Preserve it and review the session in Gas City; start a separate BB thread if it cannot be correlated safely.");
      const base = new Set(turn.baselineMessageIds);
      const promptIndex = messages.findIndex(message => message.role === "user" && !base.has(message.id) &&
        createHash("sha256").update(message.user_prompt?.text ?? message.blocks.filter(b => b.type === "text").map(b => b.text ?? "").join("\n")).digest("hex") === turn.messageDigest);
      if (promptIndex < 0)
        throw new Error("The submitted prompt is not yet present in structured history. Delivery may still be queued; wait and retry recovery. No prompt was resent.");
      // Reuse live settlement: a planning answer before a native failure is not
      // success, and partial text, open tools, or a retry cannot be settled.
      const transcript = new Transcript({ ...snapshot, structured_messages: messages.filter((message, index) => index <= promptIndex || base.has(message.id)) });
      transcript.apply(snapshot);
      const outcome = transcript.outcome();
      if (!outcome) throw new Error("The submitted prompt has no settled outcome in structured history. Wait and retry recovery. No prompt was resent.");
      receipt.turn.state = outcome.status;
    }
    await journal.put(threadId, receipt);
    return receipt;
  });
}
