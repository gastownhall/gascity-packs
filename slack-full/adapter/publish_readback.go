// Publish readback requires exact message timestamp equality and canonicalized
// text equality for keyed and unkeyed messages alike. Thread replies are read
// through conversations.replies. The publish receipt store preserves this
// evidence across restarts; message text contains no delivery bookkeeping.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"maps"
	"net/http"
	"net/url"
	"regexp"
	"slices"
	"strings"
	"time"
	"unicode"
)

const slackReadbackResponseLimit = 1 << 20

// Readback classifications. These are the adapter's own vocabulary and never
// reach the wire on their own: slackReadbackReceiptFailure maps them onto gc's
// closed PublishFailureKind set and carries the value here as receipt metadata
// instead. See that function for why.
const (
	slackReadbackUnconfirmed = "readback_unconfirmed"
	slackReadbackUnavailable = "readback_unavailable"
	slackReadbackAuth        = "readback_auth"
)

// gc's PublishFailureKind vocabulary, as far as this file needs it
// (gascity internal/extmsg/types.go: unsupported|transient|rate_limited|
// permanent|auth|not_found). Named here so the mapping below reads as a
// mapping rather than as bare strings.
const (
	publishFailureTransient = "transient"
	publishFailurePermanent = "permanent"
	publishFailureAuth      = "auth"
)

// receiptMetadataKeyReadback carries the readback classification that
// PublishFailureKind cannot express. Metadata is the only additive channel gc
// actually forwards (see publishReceipt.Metadata), so it is where the detail
// the closed enum would drop has to live.
const receiptMetadataKeyReadback = "readback"

// slackReadbackTiming bounds what the readback can cost the caller. gc gives
// the adapter a 30s budget per call (gascity internal/extmsg/http_adapter.go),
// and /publish now spends it on a write plus a read: the worst case here is
// slackPostTimeout + attempts*clientTimeout + (attempts-1)*delay =
// 10 + 3*4 + 2*0.2 = 22.4s, which leaves headroom inside that budget instead
// of racing it. TestSlackReadbackTimingDefaults pins these numbers.
type slackReadbackTiming struct {
	// attempts is the total number of readback GETs, not the number of
	// retries after the first.
	attempts int
	// delay separates those attempts.
	delay time.Duration
	// clientTimeout bounds one GET.
	clientTimeout time.Duration
}

// slackReadbackTimings is a var so tests can shorten the window; production
// code never assigns it.
var slackReadbackTimings = slackReadbackTiming{
	attempts:      3,
	delay:         200 * time.Millisecond,
	clientTimeout: 4 * time.Second,
}

var slackReadbackHTTPClient = &http.Client{Timeout: slackReadbackTimings.clientTimeout}

// slackReadbackTarget names the message a readback must find and the evidence
// it must find it by.
type slackReadbackTarget struct {
	// channel and messageTS identify the posted message.
	channel   string
	messageTS string
	// threadTS is set when the message was posted as a thread reply, which
	// conversations.history does not return.
	threadTS string
	// expectedText is the alias-rewritten text actually posted.
	expectedText string
}

type slackReadbackMessage struct {
	TS   string `json:"ts"`
	Text string `json:"text"`
}

type slackReadbackResponse struct {
	OK       bool                   `json:"ok"`
	Messages []slackReadbackMessage `json:"messages"`
	Error    string                 `json:"error"`
}

type slackReadbackError struct {
	kind string
	// retryable marks the failures a bounded re-check can plausibly clear:
	// a transport blip, and a message Slack has accepted but not yet
	// indexed. A content mismatch and an auth rejection are answers, not
	// blips, and re-asking cannot change either.
	retryable bool
	err       error
}

func (e *slackReadbackError) Error() string { return e.err.Error() }

func (e *slackReadbackError) Unwrap() error { return e.err }

func readbackFailure(kind string, retryable bool, format string, args ...any) error {
	return &slackReadbackError{kind: kind, retryable: retryable, err: fmt.Errorf(format, args...)}
}

func slackReadbackFailureKind(err error) string {
	if typed, ok := err.(*slackReadbackError); ok {
		return typed.kind
	}
	return slackReadbackUnavailable
}

func slackReadbackIsRetryable(err error) bool {
	typed, ok := err.(*slackReadbackError)
	return ok && typed.retryable
}

// slackReadbackReceiptFailure maps a readback failure onto gc's
// PublishFailureKind vocabulary and returns the adapter-level detail to record
// under receiptMetadataKeyReadback.
//
// gc's PublishFailureKind is a closed, documented set. Because it is a string
// typedef, an adapter-invented value deserializes silently and every consumer
// written against the documented enum falls through its default arm — the
// receipt would carry a kind no retry policy can read. So the wire gets a value
// from gc's vocabulary and the metadata carries which readback outcome produced
// it, which is strictly more than an unknown enum value would have told anyone:
//
//   - unconfirmed → permanent. The read path answered and the message was not
//     there (or was different text). Re-posting the identical payload cannot
//     change that; the truncation path is the clearest case, since an oversized
//     body truncates the same way every time.
//   - unavailable → transient. The read leg failed, so nothing is known about
//     the message; retrying is the right response and is safe because
//     handlePublish caches this receipt for re-verification rather than
//     re-posting (see publishReceiptBlocksRepost).
//   - auth      → auth. A token missing history scope is a configuration
//     fault, and gc's vocabulary already has the word for it.
func slackReadbackReceiptFailure(err error) (kind, detail string) {
	detail = slackReadbackFailureKind(err)
	switch detail {
	case slackReadbackUnconfirmed:
		return publishFailurePermanent, detail
	case slackReadbackAuth:
		return publishFailureAuth, detail
	default:
		return publishFailureTransient, detail
	}
}

// slackEntityUnescape reverses the three entities Slack escapes when it stores
// message text. Replacer scans the input once and does not re-scan what it
// substitutes, so "&amp;lt;" unescapes to "&lt;" rather than collapsing two
// levels into "<".
var slackEntityUnescape = strings.NewReplacer("&lt;", "<", "&gt;", ">", "&amp;", "&")

// slackAngleSpan matches a well-formed <...> span, which is the shape Slack
// wraps an auto-linked URL in.
var slackAngleSpan = regexp.MustCompile(`<([^<>]*)>`)

// Code spans are literal: do not interpret link labels inside them.
var slackCodeOrAngleSpan = regexp.MustCompile("(?s)```.*?```|`[^`\n]*`|<[^<>]*>")

// Names on Slack references are display labels; the ID is their destination.
var slackReferenceTarget = regexp.MustCompile(`^(?:@[UW][A-Z0-9]+|#[CG][A-Z0-9]+|!subteam\^S[A-Z0-9]+)$`)

// slackEmojiShortcode matches one `:name:` token wherever it stands — glued
// to a word or not. Whether the token IS an emoji is decided by its name
// alone (slackIsStandardEmojiName): Slack stores a Unicode emoji as the colon
// shortcode of its STANDARD name, with no regard for its neighbours
// (`Done🎉` is stored as `Done:tada:`), so a shortcode beside letters must
// fold exactly like one standing alone, and a shortcode-shaped token whose
// name Slack has no emoji for (`items[:start_index:]`, `std::vector::iterator`,
// `12:30:45`, `s3://bucket/:customer_id:/x`) is text that stays in the
// compare, so a changed token still reads back as changed. The bundled table
// of Slack's names is the source of truth (gf-pu2 finding 3d; the gf-jr0
// vs-main gate's Major at :185 and the lane's codex rounds 1, 3, 5, 7 and 9
// were all boundary heuristics standing in for that table).
var slackEmojiShortcode = regexp.MustCompile(`:([a-z0-9_+\-]+):`)

// slackIsStandardEmojiName reports whether name is one of Slack's standard
// emoji shortcode names (slackStandardEmojiNames, generated from Slack's own
// emoji table). A custom workspace emoji is not: it is typed as a shortcode
// and stored as typed, so it compares equal on both sides without a fold.
func slackIsStandardEmojiName(name string) bool {
	_, found := slices.BinarySearch(slackStandardEmojiNames, name)
	return found
}

// slackKeycapSequence matches a keycap emoji (`1️⃣`, `#️⃣`): a digit, `#` or
// `*` followed by an optional variation selector and the combining enclosing
// keycap, which Slack stores as `:one:`, `:hash:` and the like. The base
// character goes with it, since the shortcode carries none of it.
var slackKeycapSequence = regexp.MustCompile(`[0-9#*]\x{FE0F}?\x{20E3}`)

// slackVerbatimSpan matches the text Slack stores as typed, which the fold
// copies through: a closed mrkdwn code span (a fenced block between two
// triple backticks, or an inline span between two single backticks on one
// line) and a bare URI token of any scheme (`https://…`, `s3://…`). Slack
// renders a code span as typed and auto-links a URL without touching its
// characters, so a shortcode-shaped token in either is code or a path
// segment, not an emoji — even one whose name Slack does have, such as the
// :id: of s3://bucket/:id:/x: a slice such as items[:100:], or a path
// https://example.com/:customer_id:/orders, would otherwise fold on both
// sides and a changed snippet or URL would read back as delivered (the
// lane's codex rounds 6, 8 and 9). An unclosed backtick is a literal
// character and opens no span.
var slackVerbatimSpan = regexp.MustCompile("(?s)```.*?```|`[^`\n]*`|[a-z][a-z0-9+.-]*://[^\\s<>|]+")

// Paired quotes starting a URI path segment or query value are literal units.
// Their closers cannot close an enclosing prose quote; escaped quotes stay
// inside the value. RE2 keeps an unmatched or repeated opener scan linear.
var slackURIQuotedValue = regexp.MustCompile(`[=/?:,(\[{](?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|“[^”]*”|‘[^’]*’|«[^»]*»|‹[^›]*›)`)

var slackLinkScheme = regexp.MustCompile(`^[a-zA-Z][a-zA-Z0-9+.-]*:`)
var slackAbsoluteLinkScheme = regexp.MustCompile(`^[a-zA-Z][a-zA-Z0-9+.-]*://`)

// slackNormalizeText is a test helper; production uses slackReadbackTextMatches.
// It folds the transformations Slack applies between
// chat.postMessage and conversations.history: it entity-escapes `&`, `<` and
// `>` in the stored text, auto-links bare URLs into `<url>` spans, and
// stores a Unicode emoji as its colon shortcode (`Done 🎉` reads back as
// `Done :tada:`; https://docs.slack.dev/messaging/formatting-message-text/#emoji).
//
// It is applied to BOTH sides of the compare, never to one. Normalizing only
// the expected text would require predicting Slack's output exactly — the
// auto-link shape in particular is not something this repo can pin, and the
// Unicode-to-shortcode table is Slack's, not this repo's — whereas folding
// both sides only requires that the fold be the same on each, which is
// checkable here. The fold is deliberately lossy in exactly the way Slack is
// lossy: two texts that differ only by escaping, link markup or emoji
// compare equal, because Slack cannot tell an operator which of the two it
// stored either. Divergence that survives the fold is still reported
// unconfirmed.
func slackNormalizeText(text string) string {
	return slackFoldEmoji(slackNormalizeLinks(text))
}

func slackNormalizeLinks(text string) string {
	return slackNormalizeUnescapedLinks(slackEntityUnescape.Replace(text))
}

func slackNormalizeUnescapedLinks(text string) string {
	text = slackCodeOrAngleSpan.ReplaceAllStringFunc(text, func(span string) string {
		if strings.HasPrefix(span, "`") {
			return span
		}
		body := span[1 : len(span)-1]
		target, label, labeled := strings.Cut(body, "|")
		if labeled && slackReferenceTarget.MatchString(target) {
			return target
		}
		if strings.HasPrefix(target, "mailto:") {
			address := strings.TrimPrefix(target, "mailto:")
			local, domain, email := strings.Cut(address, "@")
			if email && local != "" && domain != "" && (!labeled || label == address) {
				return address
			}
		}
		// Slack may label an auto-link with the original URL, including a
		// bare domain or www. URL with an implicit scheme. Fold only redundant labels:
		// arbitrary labels must retain their destination for the comparison.
		// https://docs.slack.dev/messaging/formatting-message-text/#links-in-retrieved-messages
		// Legacy Slack docs also show http://example.com|www.example.com:
		// https://api.slack.com/docs/attachments#links-in-retrieved-messages
		if labeled && (strings.HasPrefix(target, "http://") || strings.HasPrefix(target, "https://")) &&
			(label == target || target == "http://"+label || target == "https://"+label ||
				(strings.HasPrefix(label, "www.") && len(label) > len("www.") && target == "http://"+strings.TrimPrefix(label, "www."))) {
			return label
		}
		return body
	})
	return text
}

// slackFoldEmoji removes every emoji from text in both of its spellings: the
// colon shortcodes Slack stores, and the Unicode form that was posted —
// keycap sequences, then the emoji characters themselves (slackEmojiRunes:
// the pictographic blocks, the scattered emoji of the symbol blocks such as
// ©, the regional indicators of flags, the skin-tone modifiers), the
// zero-width joiner and variation selectors that build sequences from
// them, and the tag characters of subdivision flags. Without
// this an unkeyed publish of a message with an emoji in it read back as a
// permanent failure although Slack had delivered it (gf-4c9 round 2,
// finding 3c).
//
// Code spans and bare URLs are left as typed on both sides: the fold
// applies to the text between them only, so a shortcode-shaped token
// inside backticks or inside a URL is compared literally (an emoji inside
// a code span is a compare of what Slack stored, the refusing side, not a
// fold).
func slackFoldEmoji(text string) string {
	var out strings.Builder
	last := 0
	for _, span := range slackVerbatimSpan.FindAllStringIndex(text, -1) {
		out.WriteString(slackFoldEmojiProse(text[last:span[0]]))
		out.WriteString(text[span[0]:span[1]])
		last = span[1]
	}
	out.WriteString(slackFoldEmojiProse(text[last:]))
	return out.String()
}

// slackFoldEmojiProse removes every emoji, in both spellings, from text that
// holds no verbatim span.
func slackFoldEmojiProse(text string) string {
	text = slackKeycapSequence.ReplaceAllString(text, "")
	// Every `:name:` token whose name is a Slack standard emoji name goes,
	// wherever it stands; every other one stays as typed. Matches are
	// non-overlapping, so a run such as `:+1::skin-tone-4:` folds token by
	// token and a kept token's closing colon is not re-read.
	text = slackEmojiShortcode.ReplaceAllStringFunc(text, func(token string) string {
		if slackIsStandardEmojiName(token[1 : len(token)-1]) {
			return ""
		}
		return token
	})
	runes := []rune(text)
	out := make([]rune, 0, len(runes))
	for i, r := range runes {
		switch {
		case isSlackEmojiRune(r):
		case isEmojiSequenceGlue(r) && (i > 0 && isSlackEmojiRune(runes[i-1]) || i+1 < len(runes) && isSlackEmojiRune(runes[i+1])):
			// A joiner, variation selector, keycap or flag tag only goes with
			// an emoji beside it: in other scripts the same characters shape
			// ordinary text (a Devanagari conjunct with a zero-width joiner is
			// not the same word without it), and Slack stores them as typed
			// (the lane's codex round 4).
		default:
			out = append(out, r)
		}
	}
	return string(out)
}

// isEmojiSequenceGlue reports the characters that build an emoji sequence
// from emoji characters: the zero-width joiner, the variation selectors,
// the combining enclosing keycap and the tag characters of subdivision
// flags.
func isEmojiSequenceGlue(r rune) bool {
	switch r {
	case 0x200D, 0xFE0E, 0xFE0F, 0x20E3:
		return true
	}
	return r >= 0xE0020 && r <= 0xE007F
}

// slackEmojiRunes is the set of emoji characters the fold removes: the
// code points with Unicode's Emoji property (emoji-data.txt, Emoji=Yes,
// Unicode 15.1), minus the digits, # and * whose keycap sequences
// slackKeycapSequence handles, plus the skin-tone modifiers. These are the
// characters Slack stores as a colon shortcode. It is deliberately not a
// symbol block or a category: ⌘, box drawing, Braille, ♯ and ♭ are text
// Slack stores as typed, and folding them away would confirm a changed
// body (the lane's codex rounds 2 and 3).
var slackEmojiRunes = &unicode.RangeTable{
	R16: []unicode.Range16{
		{Lo: 0x00A9, Hi: 0x00A9, Stride: 1},
		{Lo: 0x00AE, Hi: 0x00AE, Stride: 1},
		{Lo: 0x203C, Hi: 0x203C, Stride: 1},
		{Lo: 0x2049, Hi: 0x2049, Stride: 1},
		{Lo: 0x2122, Hi: 0x2122, Stride: 1},
		{Lo: 0x2139, Hi: 0x2139, Stride: 1},
		{Lo: 0x2194, Hi: 0x2199, Stride: 1},
		{Lo: 0x21A9, Hi: 0x21AA, Stride: 1},
		{Lo: 0x231A, Hi: 0x231B, Stride: 1},
		{Lo: 0x2328, Hi: 0x2328, Stride: 1},
		{Lo: 0x23CF, Hi: 0x23CF, Stride: 1},
		{Lo: 0x23E9, Hi: 0x23F3, Stride: 1},
		{Lo: 0x23F8, Hi: 0x23FA, Stride: 1},
		{Lo: 0x24C2, Hi: 0x24C2, Stride: 1},
		{Lo: 0x25AA, Hi: 0x25AB, Stride: 1},
		{Lo: 0x25B6, Hi: 0x25B6, Stride: 1},
		{Lo: 0x25C0, Hi: 0x25C0, Stride: 1},
		{Lo: 0x25FB, Hi: 0x25FE, Stride: 1},
		{Lo: 0x2600, Hi: 0x2604, Stride: 1},
		{Lo: 0x260E, Hi: 0x260E, Stride: 1},
		{Lo: 0x2611, Hi: 0x2611, Stride: 1},
		{Lo: 0x2614, Hi: 0x2615, Stride: 1},
		{Lo: 0x2618, Hi: 0x2618, Stride: 1},
		{Lo: 0x261D, Hi: 0x261D, Stride: 1},
		{Lo: 0x2620, Hi: 0x2620, Stride: 1},
		{Lo: 0x2622, Hi: 0x2623, Stride: 1},
		{Lo: 0x2626, Hi: 0x2626, Stride: 1},
		{Lo: 0x262A, Hi: 0x262A, Stride: 1},
		{Lo: 0x262E, Hi: 0x262F, Stride: 1},
		{Lo: 0x2638, Hi: 0x263A, Stride: 1},
		{Lo: 0x2640, Hi: 0x2640, Stride: 1},
		{Lo: 0x2642, Hi: 0x2642, Stride: 1},
		{Lo: 0x2648, Hi: 0x2653, Stride: 1},
		{Lo: 0x265F, Hi: 0x2660, Stride: 1},
		{Lo: 0x2663, Hi: 0x2663, Stride: 1},
		{Lo: 0x2665, Hi: 0x2666, Stride: 1},
		{Lo: 0x2668, Hi: 0x2668, Stride: 1},
		{Lo: 0x267B, Hi: 0x267B, Stride: 1},
		{Lo: 0x267E, Hi: 0x267F, Stride: 1},
		{Lo: 0x2692, Hi: 0x2697, Stride: 1},
		{Lo: 0x2699, Hi: 0x2699, Stride: 1},
		{Lo: 0x269B, Hi: 0x269C, Stride: 1},
		{Lo: 0x26A0, Hi: 0x26A1, Stride: 1},
		{Lo: 0x26A7, Hi: 0x26A7, Stride: 1},
		{Lo: 0x26AA, Hi: 0x26AB, Stride: 1},
		{Lo: 0x26B0, Hi: 0x26B1, Stride: 1},
		{Lo: 0x26BD, Hi: 0x26BE, Stride: 1},
		{Lo: 0x26C4, Hi: 0x26C5, Stride: 1},
		{Lo: 0x26C8, Hi: 0x26C8, Stride: 1},
		{Lo: 0x26CE, Hi: 0x26CF, Stride: 1},
		{Lo: 0x26D1, Hi: 0x26D1, Stride: 1},
		{Lo: 0x26D3, Hi: 0x26D4, Stride: 1},
		{Lo: 0x26E9, Hi: 0x26EA, Stride: 1},
		{Lo: 0x26F0, Hi: 0x26F5, Stride: 1},
		{Lo: 0x26F7, Hi: 0x26FA, Stride: 1},
		{Lo: 0x26FD, Hi: 0x26FD, Stride: 1},
		{Lo: 0x2702, Hi: 0x2702, Stride: 1},
		{Lo: 0x2705, Hi: 0x2705, Stride: 1},
		{Lo: 0x2708, Hi: 0x270D, Stride: 1},
		{Lo: 0x270F, Hi: 0x270F, Stride: 1},
		{Lo: 0x2712, Hi: 0x2712, Stride: 1},
		{Lo: 0x2714, Hi: 0x2714, Stride: 1},
		{Lo: 0x2716, Hi: 0x2716, Stride: 1},
		{Lo: 0x271D, Hi: 0x271D, Stride: 1},
		{Lo: 0x2721, Hi: 0x2721, Stride: 1},
		{Lo: 0x2728, Hi: 0x2728, Stride: 1},
		{Lo: 0x2733, Hi: 0x2734, Stride: 1},
		{Lo: 0x2744, Hi: 0x2744, Stride: 1},
		{Lo: 0x2747, Hi: 0x2747, Stride: 1},
		{Lo: 0x274C, Hi: 0x274C, Stride: 1},
		{Lo: 0x274E, Hi: 0x274E, Stride: 1},
		{Lo: 0x2753, Hi: 0x2755, Stride: 1},
		{Lo: 0x2757, Hi: 0x2757, Stride: 1},
		{Lo: 0x2763, Hi: 0x2764, Stride: 1},
		{Lo: 0x2795, Hi: 0x2797, Stride: 1},
		{Lo: 0x27A1, Hi: 0x27A1, Stride: 1},
		{Lo: 0x27B0, Hi: 0x27B0, Stride: 1},
		{Lo: 0x27BF, Hi: 0x27BF, Stride: 1},
		{Lo: 0x2934, Hi: 0x2935, Stride: 1},
		{Lo: 0x2B05, Hi: 0x2B07, Stride: 1},
		{Lo: 0x2B1B, Hi: 0x2B1C, Stride: 1},
		{Lo: 0x2B50, Hi: 0x2B50, Stride: 1},
		{Lo: 0x2B55, Hi: 0x2B55, Stride: 1},
		{Lo: 0x3030, Hi: 0x3030, Stride: 1},
		{Lo: 0x303D, Hi: 0x303D, Stride: 1},
		{Lo: 0x3297, Hi: 0x3297, Stride: 1},
		{Lo: 0x3299, Hi: 0x3299, Stride: 1},
	},
	R32: []unicode.Range32{
		{Lo: 0x1F004, Hi: 0x1F004, Stride: 1},
		{Lo: 0x1F0CF, Hi: 0x1F0CF, Stride: 1},
		{Lo: 0x1F170, Hi: 0x1F171, Stride: 1},
		{Lo: 0x1F17E, Hi: 0x1F17F, Stride: 1},
		{Lo: 0x1F18E, Hi: 0x1F18E, Stride: 1},
		{Lo: 0x1F191, Hi: 0x1F19A, Stride: 1},
		{Lo: 0x1F1E6, Hi: 0x1F1FF, Stride: 1},
		{Lo: 0x1F201, Hi: 0x1F202, Stride: 1},
		{Lo: 0x1F21A, Hi: 0x1F21A, Stride: 1},
		{Lo: 0x1F22F, Hi: 0x1F22F, Stride: 1},
		{Lo: 0x1F232, Hi: 0x1F23A, Stride: 1},
		{Lo: 0x1F250, Hi: 0x1F251, Stride: 1},
		{Lo: 0x1F300, Hi: 0x1F321, Stride: 1},
		{Lo: 0x1F324, Hi: 0x1F393, Stride: 1},
		{Lo: 0x1F396, Hi: 0x1F397, Stride: 1},
		{Lo: 0x1F399, Hi: 0x1F39B, Stride: 1},
		{Lo: 0x1F39E, Hi: 0x1F3F0, Stride: 1},
		{Lo: 0x1F3F3, Hi: 0x1F3F5, Stride: 1},
		{Lo: 0x1F3F7, Hi: 0x1F4FD, Stride: 1},
		{Lo: 0x1F4FF, Hi: 0x1F53D, Stride: 1},
		{Lo: 0x1F549, Hi: 0x1F54E, Stride: 1},
		{Lo: 0x1F550, Hi: 0x1F567, Stride: 1},
		{Lo: 0x1F56F, Hi: 0x1F570, Stride: 1},
		{Lo: 0x1F573, Hi: 0x1F57A, Stride: 1},
		{Lo: 0x1F587, Hi: 0x1F587, Stride: 1},
		{Lo: 0x1F58A, Hi: 0x1F58D, Stride: 1},
		{Lo: 0x1F590, Hi: 0x1F590, Stride: 1},
		{Lo: 0x1F595, Hi: 0x1F596, Stride: 1},
		{Lo: 0x1F5A4, Hi: 0x1F5A5, Stride: 1},
		{Lo: 0x1F5A8, Hi: 0x1F5A8, Stride: 1},
		{Lo: 0x1F5B1, Hi: 0x1F5B2, Stride: 1},
		{Lo: 0x1F5BC, Hi: 0x1F5BC, Stride: 1},
		{Lo: 0x1F5C2, Hi: 0x1F5C4, Stride: 1},
		{Lo: 0x1F5D1, Hi: 0x1F5D3, Stride: 1},
		{Lo: 0x1F5DC, Hi: 0x1F5DE, Stride: 1},
		{Lo: 0x1F5E1, Hi: 0x1F5E1, Stride: 1},
		{Lo: 0x1F5E3, Hi: 0x1F5E3, Stride: 1},
		{Lo: 0x1F5E8, Hi: 0x1F5E8, Stride: 1},
		{Lo: 0x1F5EF, Hi: 0x1F5EF, Stride: 1},
		{Lo: 0x1F5F3, Hi: 0x1F5F3, Stride: 1},
		{Lo: 0x1F5FA, Hi: 0x1F64F, Stride: 1},
		{Lo: 0x1F680, Hi: 0x1F6C5, Stride: 1},
		{Lo: 0x1F6CB, Hi: 0x1F6D2, Stride: 1},
		{Lo: 0x1F6D5, Hi: 0x1F6D7, Stride: 1},
		{Lo: 0x1F6DC, Hi: 0x1F6E5, Stride: 1},
		{Lo: 0x1F6E9, Hi: 0x1F6E9, Stride: 1},
		{Lo: 0x1F6EB, Hi: 0x1F6EC, Stride: 1},
		{Lo: 0x1F6F0, Hi: 0x1F6F0, Stride: 1},
		{Lo: 0x1F6F3, Hi: 0x1F6FC, Stride: 1},
		{Lo: 0x1F7E0, Hi: 0x1F7EB, Stride: 1},
		{Lo: 0x1F7F0, Hi: 0x1F7F0, Stride: 1},
		{Lo: 0x1F90C, Hi: 0x1F93A, Stride: 1},
		{Lo: 0x1F93C, Hi: 0x1F945, Stride: 1},
		{Lo: 0x1F947, Hi: 0x1F9FF, Stride: 1},
		{Lo: 0x1FA70, Hi: 0x1FA7C, Stride: 1},
		{Lo: 0x1FA80, Hi: 0x1FA89, Stride: 1},
		{Lo: 0x1FA8F, Hi: 0x1FAC6, Stride: 1},
		{Lo: 0x1FACE, Hi: 0x1FADC, Stride: 1},
		{Lo: 0x1FADF, Hi: 0x1FAE9, Stride: 1},
		{Lo: 0x1FAF0, Hi: 0x1FAF8, Stride: 1},
	},
	LatinOffset: 2,
}

func isSlackEmojiRune(r rune) bool {
	return unicode.Is(slackEmojiRunes, r)
}

// readBackPublishedMessage verifies a post through Slack's read API rather
// than trusting chat.postMessage's write response as delivery evidence.
//
// Retryable failures get a bounded re-check: conversations.history offers no
// read-your-writes guarantee, so a message Slack has accepted can be missing
// from the very next read purely because indexing has not caught up. Reporting
// that first empty read as "confirmed absent" would be a false negative on the
// delivery-evidence contract, and the caller's response to it is to post again.
func readBackPublishedMessage(client *http.Client, token string, target slackReadbackTarget) error {
	attempts := slackReadbackTimings.attempts
	if attempts < 1 {
		attempts = 1
	}
	var err error
	for attempt := 1; ; attempt++ {
		err = readBackPublishedMessageOnce(client, token, target)
		if err == nil {
			return nil
		}
		if attempt >= attempts || !slackReadbackIsRetryable(err) {
			return err
		}
		time.Sleep(slackReadbackTimings.delay)
	}
}

func readBackPublishedMessageOnce(client *http.Client, token string, target slackReadbackTarget) error {
	if client == nil {
		client = http.DefaultClient
	}
	request, err := newSlackReadbackRequest(token, target.channel, target.messageTS, target.threadTS)
	if err != nil {
		// A malformed request is this process's own fault and re-issuing it
		// produces the same error, so it is not retryable.
		return readbackFailure(slackReadbackUnavailable, false, "build Slack readback: %w", err)
	}
	response, err := client.Do(request)
	if err != nil {
		return readbackFailure(slackReadbackUnavailable, true, "Slack readback request: %w", err)
	}
	defer response.Body.Close()

	body, err := io.ReadAll(io.LimitReader(response.Body, slackReadbackResponseLimit+1))
	if err != nil {
		return readbackFailure(slackReadbackUnavailable, true, "read Slack readback response: %w", err)
	}
	if len(body) > slackReadbackResponseLimit {
		return readbackFailure(slackReadbackUnavailable, false, "Slack readback response exceeds %d bytes", slackReadbackResponseLimit)
	}
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		return readbackFailure(slackReadbackUnavailable, true, "Slack readback HTTP %d: %s", response.StatusCode, clipBodyForLog(body))
	}

	var result slackReadbackResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return readbackFailure(slackReadbackUnavailable, false, "decode Slack readback response: %w", err)
	}
	if !result.OK {
		// An auth-class rejection is a configuration fault, not an instrument
		// blip: the same token will be refused on every re-check, and a caller
		// that reads the kind should be told to fix the token rather than to
		// retry. /publish-file already classifies these through mapSlackError;
		// this arm keeps the readback leg consistent with it.
		switch result.Error {
		case "invalid_auth", "not_authed", "token_revoked", "missing_scope":
			return readbackFailure(slackReadbackAuth, false, "Slack readback rejected: %s", result.Error)
		}
		return readbackFailure(slackReadbackUnavailable, true, "Slack readback rejected: %s", result.Error)
	}
	for _, message := range result.Messages {
		if message.TS != target.messageTS {
			continue
		}
		return matchReadbackMessage(message, target)
	}
	return readbackFailure(slackReadbackUnconfirmed, true,
		"Slack message %s not present in channel %s readback", target.messageTS, target.channel)
}

// matchReadbackMessage decides whether the message Slack stored at this ts is
// the message that was posted.
//
// It cannot be a byte compare against what was posted. Slack canonicalizes text
// at ingestion, so a delivered message containing `&`, `<`, `>` or a bare URL
// reads back as different bytes than were sent — and agent traffic through this
// adapter is mostly PR links, dashboards and shell snippets, so that is the
// common shape, not a corner. A byte compare therefore reports Delivered:false
// for messages that are sitting in the channel, and because a non-delivered
// receipt is not cached (publishReceiptBlocksRepost), the caller's retry
// re-posts and fails the same deterministic way.
//
// Both keyed and unkeyed publishes use the same content check after the caller
// has selected the exact message timestamp.
func matchReadbackMessage(message slackReadbackMessage, target slackReadbackTarget) error {
	if message.Text == target.expectedText {
		return nil
	}
	if !slackReadbackTextMatches(target.expectedText, message.Text) {
		return readbackFailure(slackReadbackUnconfirmed, false,
			"Slack readback content mismatch for message %s", target.messageTS)
	}
	return nil
}

// confirmPublishReceipt runs the readback for a write Slack accepted and
// records what it proved on the receipt. It is the only place Delivered is set
// for a successful post: chat.postMessage's own answer is not delivery
// evidence, which is the premise this whole path exists to enforce.
func confirmPublishReceipt(token string, receipt *publishReceipt, target slackReadbackTarget) {
	err := readBackPublishedMessage(slackReadbackHTTPClient, token, target)
	if err == nil {
		receipt.Delivered = true
		receipt.FailureKind = ""
		// A re-verified receipt must not keep the detail from the read that
		// failed, or a caller would see a delivered receipt still blaming the
		// readback.
		delete(receipt.Metadata, receiptMetadataKeyReadback)
		return
	}
	log.Printf("slack readback failed: %v", err)
	kind, detail := slackReadbackReceiptFailure(err)
	receipt.Delivered = false
	receipt.FailureKind = kind
	if receipt.Metadata == nil {
		receipt.Metadata = map[string]string{}
	}
	receipt.Metadata[receiptMetadataKeyReadback] = detail
}

// replayPublishReceipt answers a retry on an idempotency key that already
// produced a receipt, without posting to Slack again.
//
// A delivered receipt is returned as it stands. A posted-but-unconfirmed one —
// a write Slack accepted whose read leg was unavailable — is re-verified
// instead: the message very probably exists, so the one thing this must not do
// is post it a second time. Only a readback that positively reports the message
// absent releases the key, and then by returning ok=false so the caller's
// normal post path runs.
func replayPublishReceipt(
	token string,
	dedup *publishDedupCache,
	key string,
	target slackReadbackTarget,
) (publishReceipt, bool) {
	cached, ok := dedup.Get(key)
	if !ok {
		return publishReceipt{}, false
	}
	// Get returns a shallow receipt copy. Keep readback mutations and the
	// caller's persistence-error metadata private to this replay.
	cached.Metadata = maps.Clone(cached.Metadata)
	if cached.Delivered {
		return cached, true
	}
	if cached.readbackTarget.messageTS != "" {
		// Reverify what this key originally posted, even after an alias reload.
		target = cached.readbackTarget
	}
	target.messageTS = cached.MessageID
	confirmPublishReceipt(token, &cached, target)
	if !cached.Delivered && cached.Metadata[receiptMetadataKeyReadback] == slackReadbackUnconfirmed {
		log.Printf("publish: dedup re-verify idem=%s ts=%s -> Slack does not have the message; releasing the key",
			key, cached.MessageID)
		dedup.Delete(key)
		// Let the handler persist this readback even if the next post fails.
		return cached, false
	}
	dedup.Put(key, cached)
	return cached, true
}

func newSlackReadbackRequest(token, channel, messageTS, threadTS string) (*http.Request, error) {
	if token == "" || channel == "" || messageTS == "" {
		return nil, fmt.Errorf("Slack readback requires token, channel, and message ts")
	}
	query := url.Values{
		"channel":   {channel},
		"oldest":    {messageTS},
		"latest":    {messageTS},
		"inclusive": {"true"},
		"limit":     {"1"},
	}
	method := "conversations.history"
	if threadTS != "" {
		method = "conversations.replies"
		query.Set("ts", threadTS)
		// Slack includes the thread parent in conversations.replies even when
		// the time range selects a reply. Leave room for that parent and the
		// exact posted reply; the timestamp match above remains exact.
		query.Set("limit", "2")
	}
	request, err := http.NewRequest(http.MethodGet, slackAPIBase+"/"+method+"?"+query.Encode(), nil)
	if err != nil {
		return nil, fmt.Errorf("build Slack readback request: %w", err)
	}
	request.Header.Set("Authorization", "Bearer "+token)
	return request, nil
}
