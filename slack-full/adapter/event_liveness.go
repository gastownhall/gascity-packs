package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

const eventLivenessInterval = 10 * time.Second

type eventLivenessState struct {
	LastEventAt   time.Time `json:"last_event_at"`
	LastEventType string    `json:"last_event_type"`
	Count         uint64    `json:"count"`
}

type eventLivenessRecorder struct {
	mu        sync.Mutex
	path      string
	state     eventLivenessState
	scheduled bool
	dirty     bool
	loaded    bool
}

func (rec *eventLivenessRecorder) record(raw json.RawMessage) {
	var event struct {
		Type    string `json:"type"`
		BotID   string `json:"bot_id"`
		Subtype string `json:"subtype"`
	}
	if err := json.Unmarshal(raw, &event); err != nil {
		log.Printf("event callback metadata decode failed: %v", err)
	}
	log.Printf("event callback: type=%q bot_authored=%t", event.Type, event.BotID != "" || event.Subtype == "bot_message")
	rec.mu.Lock()
	rec.state.LastEventAt = time.Now().UTC()
	rec.state.LastEventType = event.Type
	rec.state.Count++
	rec.dirty = true
	if !rec.scheduled {
		rec.scheduled = true
		time.AfterFunc(0, rec.flush)
	}
	rec.mu.Unlock()
}

func (rec *eventLivenessRecorder) load() error {
	if rec.loaded {
		return nil
	}
	data, err := os.ReadFile(rec.path)
	var previous eventLivenessState
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if err == nil {
		if err := json.Unmarshal(data, &previous); err != nil {
			log.Printf("event liveness state unreadable, starting a new count: %v", err)
			previous = eventLivenessState{}
		}
	}
	rec.mu.Lock()
	rec.state.Count += previous.Count
	rec.mu.Unlock()
	rec.loaded = true
	return nil
}

func (rec *eventLivenessRecorder) flush() {
	started := time.Now()
	rec.mu.Lock()
	if !rec.dirty {
		rec.scheduled = false
		rec.mu.Unlock()
		return
	}
	rec.dirty = false
	rec.mu.Unlock()
	if err := rec.load(); err != nil {
		log.Printf("event liveness write failed: %v", err)
		time.AfterFunc(time.Until(started.Add(eventLivenessInterval)), rec.flush)
		return
	}
	rec.mu.Lock()
	snapshot := rec.state
	rec.dirty = false
	rec.mu.Unlock()
	data, err := json.Marshal(snapshot)
	if err == nil {
		err = writeFile0600WithSync(rec.path, data)
	}
	if err != nil {
		log.Printf("event liveness write failed: %v", err)
	}
	time.AfterFunc(time.Until(started.Add(eventLivenessInterval)), rec.flush)
}

type outboundLivenessState struct {
	LastOutboundAt time.Time `json:"last_outbound_at"`
}

var outboundLivenessMu sync.Mutex

func recordOutboundLiveness(channel, timestamp string) {
	if !strings.HasPrefix(channel, "C") && !strings.HasPrefix(channel, "G") {
		return
	}
	if err := saveOutboundLiveness(timestamp); err != nil {
		log.Printf("outbound liveness write failed: %v", err)
	}
}

func saveOutboundLiveness(timestamp string) error {
	seconds, fraction, ok := strings.Cut(timestamp, ".")
	sec, err := strconv.ParseInt(seconds, 10, 64)
	if err != nil || !ok || len(fraction) > 9 {
		return fmt.Errorf("invalid Slack post timestamp %q", timestamp)
	}
	nano, err := strconv.ParseInt(fraction+strings.Repeat("0", 9-len(fraction)), 10, 64)
	if err != nil {
		return err
	}
	state := outboundLivenessState{LastOutboundAt: time.Unix(sec, nano).UTC()}
	path := companyStateDirDefault(os.Getenv("GC_CITY_PATH"), "outbound-liveness.json")
	outboundLivenessMu.Lock()
	defer outboundLivenessMu.Unlock()
	data, err := os.ReadFile(path)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if err == nil {
		var previous outboundLivenessState
		if err := json.Unmarshal(data, &previous); err != nil {
			return err
		}
		if !state.LastOutboundAt.After(previous.LastOutboundAt) {
			return nil
		}
	}
	data, err = json.Marshal(state)
	if err != nil {
		return err
	}
	return writeFile0600WithSync(path, data)
}
