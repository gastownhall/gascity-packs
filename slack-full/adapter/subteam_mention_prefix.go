package main

import "strings"

// parseSubteamMentionPrefix recognizes a Slack User Group ("subteam")
// mention token at the start of the trimmed text and extracts (1) the
// optional `@handle` label and (2) the subteam ID, plus the trailing
// remainder. Slack delivers two shapes depending on context:
//
//	Labeled:    <!subteam^TEAMID|@handle>
//	Unlabeled:  <!subteam^TEAMID>
//
// The labeled form is what Slack emits when a human picks a User Group
// from native @-autocomplete in text mode; the unlabeled form is what
// arrives in some event payloads (e.g. when the User Group is mentioned
// inline by Slack on the server side). Both shapes occur in production
// and both must be normalized to the same address-by-handle dispatch
// path — that's the gpk-hmr.2 contract.
//
// Return values:
//
//   - handle:     non-empty for the labeled form (the `@`-stripped
//                 label); empty for the unlabeled form.
//   - subteamID:  the Slack User Group ID (e.g. "S0123ABCD") in both
//                 shapes. Non-empty whenever ok=true.
//   - remainder:  the text after the closing `>`, with one optional
//                 colon and one leading whitespace byte trimmed
//                 (mirroring parseHandlePrefix's separator rules).
//   - ok:         true on any well-formed subteam token at the head;
//                 false otherwise.
//
// Caller responsibilities:
//
//   - The labeled form is gated against handleAliasRegistry by the
//     caller, matching the existing `@handle:` semantics from gpk-2zi.
//   - The unlabeled form is gated against the operator-configured
//     subteamAliasMap (subteam_id → handle) by the caller — without
//     the map there is no way to know which gc handle a subteam ID
//     belongs to.
//
// Semantics (mirroring parseHandlePrefix where they apply):
//
//   - Leading whitespace is tolerated; the token must start at the
//     trimmed text's first byte.
//   - For the labeled form, the label is the run of [A-Za-z0-9_-]
//     after an OPTIONAL single leading `@`. Slack's native
//     @-autocomplete emits `|@handle`, but a User Group mention typed
//     by a human commonly arrives as `|handle` with no `@` — both are
//     accepted and normalized to the same `@`-stripped handle. Empty
//     label, a bare `@`, or a label containing any other character
//     returns ok=false (operators should populate subteamAliasMap
//     directly rather than relying on a malformed label).
//   - For the unlabeled form, TEAMID is everything between `^` and
//     `>`; empty TEAMID returns ok=false.
//   - After the closing `>`, any leading colon (`:`) is trimmed,
//     followed by one leading whitespace byte.
//
// Cases that return ("", "", "", false):
//
//   - text whose trimmed head is not `<!subteam^`
//   - missing closing `>`
//   - empty subteam ID (`<!subteam^>`, `<!subteam^|@h>`)
//   - empty label in the labeled form (`<!subteam^Sxxx|>` or `<!subteam^Sxxx|@>`)
//   - label with an invalid character (`<!subteam^X|@bad.handle>`)
//
// On any non-match the returned strings are empty so the caller cannot
// accidentally consume input from a miss — same discipline as
// parseDoubleHandlePrefix.
func parseSubteamMentionPrefix(text string) (handle, subteamID, remainder string, ok bool) {
	const head = "<!subteam^"
	trimmed := strings.TrimLeft(text, " \t")
	if !strings.HasPrefix(trimmed, head) {
		return "", "", "", false
	}
	rest := trimmed[len(head):]

	closer := strings.IndexByte(rest, '>')
	if closer < 0 {
		return "", "", "", false
	}
	inside := rest[:closer]
	body := rest[closer+1:]

	// Split inside on the first `|` to detect the labeled form. The
	// unlabeled form has no pipe; both forms must yield a non-empty
	// subteam ID.
	pipe := strings.IndexByte(inside, '|')
	var sid, label string
	if pipe < 0 {
		sid = inside
	} else {
		sid = inside[:pipe]
		label = inside[pipe+1:]
	}
	if sid == "" {
		return "", "", "", false
	}

	var parsedHandle string
	if pipe >= 0 {
		// Labeled form: accept `@handle` (Slack @-autocomplete) and the
		// bare `handle` shape (human-typed User Group mention — Slack
		// omits the `@` in the label for those). Strip one optional
		// leading `@`, then require the remainder be a valid handle
		// character run. An empty label, or a label that is just `@`,
		// leaves an empty candidate and is rejected below.
		candidate := label
		if len(candidate) > 0 && candidate[0] == '@' {
			candidate = candidate[1:]
		}
		handleEnd := 0
		for i := 0; i < len(candidate); i++ {
			r := candidate[i]
			if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') ||
				(r >= '0' && r <= '9') || r == '-' || r == '_' {
				handleEnd = i + 1
			} else {
				break
			}
		}
		if handleEnd == 0 || handleEnd != len(candidate) {
			return "", "", "", false
		}
		parsedHandle = candidate
	}

	if body == "" {
		return parsedHandle, sid, "", true
	}
	// Optional `:` separator after the token, mirroring parseHandlePrefix
	// ("@handle:" vs "@handle ").
	if body[0] == ':' {
		body = body[1:]
	}
	// One leading whitespace byte trimmed, again mirroring parseHandlePrefix.
	if len(body) > 0 && (body[0] == ' ' || body[0] == '\t' || body[0] == '\n') {
		body = body[1:]
	}
	return parsedHandle, sid, body, true
}
