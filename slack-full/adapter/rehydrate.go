package main

// rehydrate.go — replay locally-recorded room bindings to gc after the
// adapter (re-)registers.
//
// Why: gc-side conversation groups / participants / bindings do NOT
// rehydrate when the adapter re-registers after a from-dead recovery
// (fresh pack cache clone / gc restart). The pack's `bind-room` command
// records every binding it creates under
//
//	<GC_CITY_PATH>/.gc/services/slack/data/config.json
//
// so on (re-)registration this replays those records back to gc,
// restoring bindings that would otherwise present as "no active binding"
// 422s — without a human re-running `gc slack bind-room`.
//
// Faithful to scripts/slack_chat_bind_room.py's POST sequence:
//
//	1. POST /extmsg/groups       {root_conversation, mode:"launcher", default_handle, [fanout_policy]}
//	2. POST /extmsg/participants {group_id, handle, session_id, public:true}   (per participant)
//	3. POST /extmsg/bind         {session_id: binding_owner, conversation}     (if an owner was recorded)
//
// Idempotency: /extmsg/groups is ensure-by-root_conversation and
// /extmsg/participants is upsert — bind_room.py re-runs both on every
// re-bind with no conflict handling, so they must be idempotent.
// /extmsg/bind is 1:1 per conversation and returns a conflict when the
// conversation is already bound (the clean-restart case); that conflict is
// the desired end-state, so it is tolerated, not treated as a failure.
//
// Every step is best-effort and LOUD: a failure is logged and the next
// binding still runs; the adapter never dies on a rehydrate error (a human
// `gc slack bind-room` stays the documented fallback). REVIEW NOTE: the
// group ensure-semantics assumption is inferred from bind_room.py (the gc
// source is not in this repo) — worth a live confirmation before landing.

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// packStateConfig mirrors the subset of
// <GC_CITY_PATH>/.gc/services/slack/data/config.json written by
// slack_chat_bind_room.py that rehydration needs.
type packStateConfig struct {
	Bindings map[string]storedBinding `json:"bindings"`
}

type storedBinding struct {
	Kind          string              `json:"kind"`
	Conversation  conversationRef     `json:"conversation"`
	GroupID       string              `json:"group_id"`
	DefaultHandle string              `json:"default_handle"`
	FanoutPolicy  json.RawMessage     `json:"fanout_policy"` // opaque; may be JSON null
	Participants  []storedParticipant `json:"participants"`
	BindingOwner  string              `json:"binding_owner"` // may be "" / JSON null
}

type storedParticipant struct {
	Handle      string `json:"handle"`
	SessionName string `json:"session_name"`
}

type rehydrateSummary struct {
	total    int
	restored int
	failed   int
}

// packConfigPath is the on-disk location bind_room.py writes bindings to,
// rooted at GC_CITY_PATH (see slack_intake_common.pack_state_dir).
func packConfigPath(cityPath string) string {
	return filepath.Join(cityPath, ".gc", "services", "slack", "data", "config.json")
}

// rehydrateBindings loads the pack binding config and replays every
// recorded binding to gc. Best-effort and non-fatal — see file header.
func rehydrateBindings(cfg config) rehydrateSummary {
	return rehydrateBindingsWith(cfg, http.DefaultClient, defaultGCRetryConfig(), time.Sleep)
}

// rehydrateBindingsWith is the testable core: the HTTP client, retry
// policy, and sleep are injected.
func rehydrateBindingsWith(cfg config, client *http.Client, rc gcRetryConfig, sleep func(time.Duration)) rehydrateSummary {
	var sum rehydrateSummary
	if cfg.cityPath == "" {
		log.Printf("WARN: binding rehydrate skipped: GC_CITY_PATH unset, cannot locate pack config")
		return sum
	}
	path := packConfigPath(cfg.cityPath)
	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			log.Printf("binding rehydrate: no pack config at %s (nothing to rehydrate)", path)
			return sum
		}
		log.Printf("WARN: binding rehydrate: cannot read %s: %v", path, err)
		return sum
	}
	var pc packStateConfig
	if err := json.Unmarshal(raw, &pc); err != nil {
		log.Printf("WARN: binding rehydrate: corrupt pack config %s: %v", path, err)
		return sum
	}
	if len(pc.Bindings) == 0 {
		log.Printf("binding rehydrate: pack config has no bindings (nothing to rehydrate)")
		return sum
	}

	// Deterministic order for stable, greppable logs.
	keys := make([]string, 0, len(pc.Bindings))
	for k := range pc.Bindings {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	log.Printf("binding rehydrate: replaying %d binding(s) from %s", len(keys), path)
	for _, key := range keys {
		sum.total++
		if err := rehydrateOne(cfg, client, rc, sleep, key, pc.Bindings[key]); err != nil {
			log.Printf("WARN: binding rehydrate: %s FAILED (run `gc slack bind-room` to restore it): %v", key, err)
			sum.failed++
			continue
		}
		sum.restored++
	}
	log.Printf("binding rehydrate: done — %d/%d restored (%d failed)", sum.restored, sum.total, sum.failed)
	return sum
}

// rehydrateOne replays a single stored binding's group → participants →
// bind sequence. Returns an error only for a genuine, unrecovered failure
// (a bind conflict is tolerated as the already-bound end-state).
func rehydrateOne(cfg config, client *http.Client, rc gcRetryConfig, sleep func(time.Duration), key string, b storedBinding) error {
	base := fmt.Sprintf("%s/v0/city/%s", cfg.gcAPIBase, url.PathEscape(cfg.cityName))

	// 1. ensure the launcher-mode group exists (idempotent by root_conversation).
	groupBody := map[string]any{
		"root_conversation": b.Conversation,
		"mode":              "launcher",
		"default_handle":    b.DefaultHandle,
	}
	if hasFanoutPolicy(b.FanoutPolicy) {
		groupBody["fanout_policy"] = b.FanoutPolicy
	}
	gb, err := json.Marshal(groupBody)
	if err != nil {
		return fmt.Errorf("marshal group: %w", err)
	}
	respBody, err := gcPostWithRetry(client, rc, sleep, base+"/extmsg/groups", "rehydrate-group["+key+"]", gb)
	if err != nil {
		return fmt.Errorf("ensure group: %w", err)
	}
	var groupResp struct {
		ID string `json:"ID"`
	}
	if err := json.Unmarshal(respBody, &groupResp); err != nil {
		return fmt.Errorf("parse group response: %w", err)
	}
	groupID := groupResp.ID
	if groupID == "" {
		groupID = b.GroupID // fall back to the recorded id if gc echoed none
	}
	if groupID == "" {
		return fmt.Errorf("ensure group: neither response nor record carried a group id")
	}

	// 2. upsert each participant membership (idempotent).
	for _, p := range b.Participants {
		pb, err := json.Marshal(map[string]any{
			"group_id":   groupID,
			"handle":     p.Handle,
			"session_id": p.SessionName,
			"public":     true,
		})
		if err != nil {
			return fmt.Errorf("marshal participant %s: %w", p.Handle, err)
		}
		if _, err := gcPostWithRetry(client, rc, sleep, base+"/extmsg/participants", "rehydrate-participant["+p.Handle+"]", pb); err != nil {
			return fmt.Errorf("upsert participant %s=%s: %w", p.Handle, p.SessionName, err)
		}
	}

	// 3. re-bind the publisher/owner (required for /extmsg/outbound). A
	// conflict means the binding already exists — the desired state.
	if b.BindingOwner != "" {
		bb, err := json.Marshal(map[string]any{
			"session_id":   b.BindingOwner,
			"conversation": b.Conversation,
		})
		if err != nil {
			return fmt.Errorf("marshal bind: %w", err)
		}
		if _, err := gcPostWithRetry(client, rc, sleep, base+"/extmsg/bind", "rehydrate-bind["+b.BindingOwner+"]", bb); err != nil {
			if isBindingConflict(err) {
				log.Printf("binding rehydrate: %s already bound to %s (conflict tolerated)", key, b.BindingOwner)
			} else {
				return fmt.Errorf("bind owner %s: %w", b.BindingOwner, err)
			}
		}
	}

	log.Printf("binding rehydrate: %s restored (group=%s participants=%d owner=%q)", key, groupID, len(b.Participants), b.BindingOwner)
	return nil
}

// hasFanoutPolicy reports whether a recorded fanout_policy value is a real
// object rather than absent or JSON null.
func hasFanoutPolicy(raw json.RawMessage) bool {
	s := strings.TrimSpace(string(raw))
	return s != "" && s != "null"
}

// isBindingConflict reports whether err looks like gc rejecting a bind
// because the conversation is already bound (clean-restart case), in which
// case the existing binding is the desired end-state and the bind is a
// no-op success rather than a failure.
func isBindingConflict(err error) bool {
	if err == nil {
		return false
	}
	s := strings.ToLower(err.Error())
	return strings.Contains(s, "409") ||
		strings.Contains(s, "conflict") ||
		strings.Contains(s, "already bound")
}
