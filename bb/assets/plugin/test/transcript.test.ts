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
