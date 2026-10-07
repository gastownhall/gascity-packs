import test from "node:test";
import assert from "node:assert/strict";
import { Transcript } from "../src/transcript.js";
import { frame } from "./fixture.js";
import { parseSSE } from "../src/client.js";

test("partial/upsert replay, tools, final+idle completion, and reset fail honestly", () => {
  const transcript = new Transcript(frame("s1"));
  const text = (status: string, value: string) => ({ id: "m1", role: "assistant", status, blocks: [{ type: "text", text: value }] });
  const partial = frame("s1", [text("partial", "Hel")], "in_turn", "upsert");
  assert.equal(transcript.apply(partial).filter(d => d.kind === "item.textDelta").length, 1);
  assert.deepEqual(transcript.apply(partial), []);
  assert.equal(transcript.complete(), false);
  const final = frame("s1", [text("final", "Hello")], "idle", "upsert");
  assert.equal(transcript.apply(final).find(d => d.kind === "item.textDelta")?.text, "lo");
  assert.equal(transcript.complete(), true);
  assert.throws(() => transcript.apply({ ...final, operation: "reset" }), /rewrote/);
});

test("SSE handles fragmented UTF-8, CRLF, comments and multiline data", async () => {
  const encoded = new TextEncoder().encode(': heartbeat\r\nevent: structured\r\nid: token\r\ndata: {"text":\r\ndata: "café"}\r\n\r\n');
  const body = new ReadableStream({ start(controller) { for (const byte of encoded) controller.enqueue(Uint8Array.of(byte)); controller.close(); } });
  const result = []; for await (const event of parseSSE(body)) result.push(event);
  assert.equal(result.length, 1); assert.equal(result[0]!.event, "structured"); assert.equal(result[0]!.id, "token"); assert.deepEqual(JSON.parse(result[0]!.data), { text: "café" });
});


test("unknown runtime activity never reports successful completion", () => {
  const transcript = new Transcript(frame("s1"));
  assert.throws(() => transcript.apply(frame("s1", [{ id: "answer", role: "assistant", status: "final", blocks: [{ type: "text", text: "Done" }] }], "unknown")), /cannot report reliable turn activity/);
  assert.equal(transcript.complete(), false);
});


test("later turns require the complete new prompt before presenting an answer", () => {
  const user = { id: "old-user", role: "user", status: "final", blocks: [{ type: "text", text: "full prompt" }] };
  const transcript = new Transcript(frame("s1", [user]), "full prompt");
  const answer = { id: "answer", role: "assistant", status: "final", blocks: [{ type: "text", text: "Done" }] };
  assert.deepEqual(transcript.apply(frame("s1", [user, { ...user, id: "truncated", blocks: [{ type: "text", text: "prompt" }] }, answer])), []);
  assert.equal(transcript.complete(), false);
  assert.equal(transcript.waitingForPrompt, true);
  const valid = new Transcript(frame("s1", [user]), "full prompt");
  assert.ok(valid.apply(frame("s1", [user, { ...user, id: "new-user" }, answer])).length);
  assert.equal(valid.complete(), true);
});

test("typed native outcomes use ordered current-turn records after the whole frame", () => {
  const user = { id: "prompt", role: "user", status: "final", blocks: [{ type: "text", text: "Complete prompt" }] };
  const answer = { id: "answer", role: "assistant", status: "final", blocks: [{ type: "text", text: "API Error is ordinary quoted text" }] };
  const error = { id: "error", role: "system", status: "final", system_event: { kind: "error", category: "provider_error", message: "Native failure" }, blocks: [{ type: "text", text: "Native failure" }] };
  const retry = { ...error, id: "retry", system_event: { kind: "retry", category: "provider_retry", message: "Provider retry in progress" } };
  for (const [label, messages, expected] of [
    ["error without assistant", [error], "failed"],
    ["planning then error", [answer, error], "failed"],
    ["error then real success in same frame", [error, answer], "completed"],
    ["retry then real success", [retry, answer], "completed"],
    ["planning then retry", [answer, retry], undefined],
    ["unfinished native error", [answer, { ...error, status: "partial" }], undefined],
    ["error then unfinished response", [error, { ...answer, status: "partial" }], undefined],
    ["ordinary error words", [answer], "completed"],
    ["other system error", [answer, { ...error, system_event: { kind: "error", category: "other", message: "Unrelated" } }], "completed"],
  ] as const) {
    const transcript = new Transcript(frame("s1"), "Complete prompt");
    transcript.apply(frame("s1", [user, ...messages]));
    assert.equal(transcript.outcome()?.status, expected, label);
  }
  const transcript = new Transcript(frame("s1", [error]), "Complete prompt");
  transcript.apply(frame("s1", [error, user, answer]));
  assert.equal(transcript.outcome()?.status, "completed", "baseline native errors are ignored");
  transcript.apply(frame("s1", [error], "idle", "upsert"));
  assert.equal(transcript.outcome()?.status, "completed", "historical replay cannot replace the outcome");
});

test("native failure requires full prompt, reliable idle, and closed text and tools", () => {
  const user = { id: "prompt", role: "user", status: "final", blocks: [{ type: "text", text: "Complete prompt" }] };
  const error = { id: "error", role: "system", status: "final", system_event: { kind: "error", category: "provider_error", message: "Native failure" }, blocks: [] };
  const assistant = { id: "answer", role: "assistant", status: "partial", blocks: [{ type: "text", text: "Planning" }] };
  const tool = { id: "tool", role: "assistant", status: "final", blocks: [{ type: "tool_use", id: "call", name: "Bash" }] };
  const result = { id: "result", role: "user", status: "final", blocks: [{ type: "tool_result", tool_call_id: "call", content: "Done" }] };
  const unproven = new Transcript(frame("s1"), "Complete prompt");
  unproven.apply(frame("s1", [error]));
  assert.equal(unproven.outcome(), undefined);
  for (const guard of ["busy", "pending", "tail-tool", "partial-text", "unclosed-tool"] as const) {
    const transcript = new Transcript(frame("s1"), "Complete prompt");
    const messages = [user, ...(guard === "partial-text" ? [assistant] : guard === "unclosed-tool" ? [tool] : []), error];
    const blocked = frame("s1", messages, guard === "busy" ? "in_turn" : "idle");
    if (guard === "pending") blocked.history.tail_state.pending_interaction_ids = ["approval"];
    if (guard === "tail-tool") blocked.history.tail_state.open_tool_call_ids = ["call"];
    transcript.apply(blocked);
    assert.equal(transcript.outcome(), undefined, guard);
    // Error stays last in ordered history even when earlier text is finalized.
    const settled = guard === "partial-text" ? [{ ...assistant, status: "final" }] : guard === "unclosed-tool" ? [result] : [];
    transcript.apply(frame("s1", settled, "idle", "upsert"));
    assert.equal(transcript.outcome()?.status, "failed", `${guard} settled`);
  }
});



test("Codex delayed usage reset preserves tool output and completes without duplicate replay", () => {
  const prompt = { id: "prompt", role: "user", status: "final", blocks: [{ type: "text", text: "Run hostname" }] };
  const call = { id: "call-message", role: "assistant", status: "final", blocks: [{ type: "tool_use", id: "call", name: "exec", input: { cmd: "hostname" } }] };
  const result = { id: "result", role: "user", status: "final", blocks: [{ type: "tool_result", tool_call_id: "call", content: "bb-provider-stage" }] };
  const answer = { id: "answer", role: "assistant", status: "final", blocks: [{ type: "text", text: "DONE" }] };
  const transcript = new Transcript(frame("s1", [prompt]));
  const opened = transcript.apply(frame("s1", [call, result], "in_turn", "upsert"));
  assert.equal(opened.filter(d => d.kind === "item.open").length, 1);
  assert.equal(opened.filter(d => d.kind === "item.close").length, 1);
  const reset = { ...frame("s1", [prompt, { ...call, model: "gpt-6-luna", usage: { input_tokens: 42, output_tokens: 8 } }, result, answer], "idle", "reset"), reset_reason: "history_rewritten" as const };
  const deltas = transcript.apply(reset);
  assert.equal(deltas.filter(d => d.kind === "item.open").length, 1, "only the new answer opens");
  assert.equal(deltas.filter(d => d.kind === "item.textDelta").map(d => d.text).join(""), "DONE");
  assert.equal(deltas.filter(d => d.kind === "item.close").length, 0, "completed tool is not replayed");
  assert.deepEqual(transcript.apply(reset), []);
  assert.equal(transcript.complete(), true);
});

test("metadata reset reconciliation rejects changed, missing or reordered conversation content atomically", () => {
  const prompt = { id: "prompt", role: "user", status: "final", blocks: [{ type: "text", text: "Run hostname" }] };
  const call = { id: "call-message", role: "assistant", status: "final", blocks: [{ type: "tool_use", id: "call", name: "exec", input: { cmd: "hostname" } }] };
  const result = { id: "result", role: "user", status: "final", blocks: [{ type: "tool_result", tool_call_id: "call", content: "bb-provider-stage" }] };
  const variants = [
    [prompt, { ...call, blocks: [{ ...call.blocks[0], input: { cmd: "other" } }] }, result],
    [prompt, call, { ...result, blocks: [{ ...result.blocks[0], content: "changed" }] }],
    [prompt, result],
    [prompt, result, call],
    [{ ...prompt, blocks: [{ type: "text", text: "Changed prompt" }] }, call, result],
    [prompt, { ...call, status: "superseded" }, result],
  ];
  for (const messages of variants) {
    const transcript = new Transcript(frame("s1", [prompt]));
    transcript.apply(frame("s1", [call, result], "in_turn", "upsert"));
    assert.throws(() => transcript.apply({ ...frame("s1", messages, "idle", "reset"), reset_reason: "history_rewritten" as const }), /rewrote/);
    assert.equal(transcript.idle, false, "failed reset must not change completion state");
  }
});
