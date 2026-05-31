// Package blockkit renders typed slack-pack status payloads (milestone,
// progress, rollup) into Slack Block Kit blocks suitable for direct
// chat.postMessage submission.
//
// Ported from cmd/gc/slack_block_kit.go (gc-nqy49) as part of the
// slack-cli relocation epic gc-coe10. Behavior identical to the
// cmd/gc original — Phase 2 deletes the original after the consumer
// (`gc slack post-message`) cuts over.
package blockkit

import (
	"errors"
	"fmt"
	"strings"
)

// Block Kit renderers for the `gc slack post-message` agent-driven status
// projection surface. These functions are pure: a typed payload in, a
// []Block out. They never call out to Slack — the CLI runner does
// that. Keeping render and transport separate lets tests assert on the
// block structure without httptest.
//
// See https://api.slack.com/block-kit for the schema. We model only the
// subset required by milestone / progress / rollup payloads.

// StatusKind names a renderer. The set is closed: each kind has a
// dedicated builder. New kinds are added as code, not config — the
// rendering shape is part of the SDK surface, not user config.
type StatusKind string

const (
	StatusKindMilestone StatusKind = "milestone"
	StatusKindProgress  StatusKind = "progress"
	StatusKindRollup    StatusKind = "rollup"
)

// StatusPayload is the typed input every renderer accepts. Fields
// are optional unless the renderer requires them; renderers fail fast
// when required fields are missing. Title is required for all kinds —
// Block Kit headers are the visual anchor for status posts.
type StatusPayload struct {
	Title    string          `json:"title"`
	Summary  string          `json:"summary,omitempty"`
	Fields   []StatusField   `json:"fields,omitempty"`
	Items    []StatusItem    `json:"items,omitempty"`
	Progress *StatusProgress `json:"progress,omitempty"`
	Footer   string          `json:"footer,omitempty"`
}

// StatusField is a label/value pair rendered as a Block Kit
// section field. Both sides are mrkdwn. Used by milestone payloads.
type StatusField struct {
	Label string `json:"label"`
	Value string `json:"value"`
}

// StatusItem is a labeled list entry for rollup payloads. Items
// are rendered as bulleted mrkdwn lines.
type StatusItem struct {
	Label string `json:"label"`
	Value string `json:"value,omitempty"`
}

// StatusProgress carries the discrete progress fraction rendered
// into a unicode bar. Total must be > 0 and Current must be in
// [0, Total]; the renderer validates this.
type StatusProgress struct {
	Current int `json:"current"`
	Total   int `json:"total"`
}

// Block is a single Block Kit element. The exported field set is
// minimal — we only emit blocks we actually use (header, section,
// context, divider). The omitempty tags keep the marshaled JSON
// idiomatic for Slack.
type Block struct {
	Type     string      `json:"type"`
	Text     *BlockText  `json:"text,omitempty"`
	Fields   []BlockText `json:"fields,omitempty"`
	Elements []BlockText `json:"elements,omitempty"`
}

// BlockText is a Block Kit text object. Type is "plain_text" or
// "mrkdwn"; Slack rejects anything else for these fields.
type BlockText struct {
	Type  string `json:"type"`
	Text  string `json:"text"`
	Emoji *bool  `json:"emoji,omitempty"`
}

// RenderStatusBlocks dispatches to the renderer for kind. The returned
// slice is safe to marshal directly into Slack chat.postMessage's
// `blocks` parameter.
func RenderStatusBlocks(kind StatusKind, p StatusPayload) ([]Block, error) {
	if strings.TrimSpace(p.Title) == "" {
		return nil, errors.New("title is required")
	}
	switch kind {
	case StatusKindMilestone:
		return renderMilestoneBlocks(p), nil
	case StatusKindProgress:
		return renderProgressBlocks(p)
	case StatusKindRollup:
		return renderRollupBlocks(p), nil
	default:
		return nil, fmt.Errorf("unknown slack status kind %q (want milestone|progress|rollup)", kind)
	}
}

func renderMilestoneBlocks(p StatusPayload) []Block {
	blocks := []Block{headerBlock(p.Title)}
	if p.Summary != "" {
		blocks = append(blocks, mrkdwnSection(p.Summary))
	}
	if len(p.Fields) > 0 {
		fields := make([]BlockText, 0, len(p.Fields))
		for _, f := range p.Fields {
			fields = append(fields, BlockText{
				Type: "mrkdwn",
				Text: fmt.Sprintf("*%s*\n%s", f.Label, f.Value),
			})
		}
		blocks = append(blocks, Block{Type: "section", Fields: fields})
	}
	if p.Footer != "" {
		blocks = append(blocks, contextBlock(p.Footer))
	}
	return blocks
}

func renderProgressBlocks(p StatusPayload) ([]Block, error) {
	if p.Progress == nil {
		return nil, errors.New("progress kind requires a progress object")
	}
	if p.Progress.Total <= 0 {
		return nil, fmt.Errorf("progress.total must be > 0, got %d", p.Progress.Total)
	}
	if p.Progress.Current < 0 || p.Progress.Current > p.Progress.Total {
		return nil, fmt.Errorf("progress.current must be in [0, %d], got %d", p.Progress.Total, p.Progress.Current)
	}
	bar := progressBar(p.Progress.Current, p.Progress.Total)
	body := fmt.Sprintf("%s  %d/%d", bar, p.Progress.Current, p.Progress.Total)
	if p.Summary != "" {
		body = p.Summary + "\n" + body
	}
	blocks := []Block{headerBlock(p.Title), mrkdwnSection(body)}
	if p.Footer != "" {
		blocks = append(blocks, contextBlock(p.Footer))
	}
	return blocks, nil
}

func renderRollupBlocks(p StatusPayload) []Block {
	blocks := []Block{headerBlock(p.Title)}
	if p.Summary != "" {
		blocks = append(blocks, mrkdwnSection(p.Summary))
	}
	if len(p.Items) > 0 {
		var b strings.Builder
		for i, it := range p.Items {
			if i > 0 {
				b.WriteString("\n")
			}
			b.WriteString("• *")
			b.WriteString(it.Label)
			b.WriteString("*")
			if it.Value != "" {
				b.WriteString(": ")
				b.WriteString(it.Value)
			}
		}
		blocks = append(blocks, mrkdwnSection(b.String()))
	}
	if p.Footer != "" {
		blocks = append(blocks, contextBlock(p.Footer))
	}
	return blocks
}

// headerBlock returns a Block Kit header block. Slack truncates header
// text at 150 chars; we leave that to Slack rather than silently
// trimming here — clearer error from the API than a guessed cut.
func headerBlock(text string) Block {
	emoji := true
	return Block{
		Type: "header",
		Text: &BlockText{
			Type:  "plain_text",
			Text:  text,
			Emoji: &emoji,
		},
	}
}

// mrkdwnSection returns a section block whose body is mrkdwn.
func mrkdwnSection(text string) Block {
	return Block{
		Type: "section",
		Text: &BlockText{Type: "mrkdwn", Text: text},
	}
}

// contextBlock returns a Block Kit context block with a single mrkdwn
// element — used for footers/timestamps that should render small.
func contextBlock(text string) Block {
	return Block{
		Type:     "context",
		Elements: []BlockText{{Type: "mrkdwn", Text: text}},
	}
}

// progressBar renders a 20-cell unicode bar for current/total. Filled
// cells are █, empty cells are ░. The width is fixed at 20 — wide
// enough to read on mobile, narrow enough to fit alongside the
// fraction without wrapping.
func progressBar(current, total int) string {
	const width = 20
	if total <= 0 {
		return strings.Repeat("░", width)
	}
	filled := current * width / total
	if filled < 0 {
		filled = 0
	}
	if filled > width {
		filled = width
	}
	return strings.Repeat("█", filled) + strings.Repeat("░", width-filled)
}
