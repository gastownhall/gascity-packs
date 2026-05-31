package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
)

// TestThreadSessionRegistryRoundTrip pins the basic durable-cache
// contract: AcquireOrCreate persists, a reload sees the same binding,
// and Lookup returns it.
func TestThreadSessionRegistryRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("newThreadSessionRegistry: %v", err)
	}
	sid, created, err := reg.AcquireOrCreate("C1", "1700000000.000100", func() (string, error) {
		return "gc-sess-1", nil
	})
	if err != nil {
		t.Fatalf("AcquireOrCreate: %v", err)
	}
	if !created {
		t.Errorf("created=false on first acquire; want true")
	}
	if sid != "gc-sess-1" {
		t.Errorf("sessionID=%q, want gc-sess-1", sid)
	}

	// Reload from disk and verify Lookup hits.
	reg2, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	got, ok := reg2.Lookup("C1", "1700000000.000100")
	if !ok {
		t.Fatal("Lookup ok=false after reload")
	}
	if got != "gc-sess-1" {
		t.Errorf("Lookup = %q, want gc-sess-1", got)
	}
}

// TestThreadSessionRegistryConcurrentAcquireOrCreateOnSameKey is the
// race-safety contract for cby.5.a: N concurrent posts in the same
// Slack thread must yield exactly one create-callback invocation; all
// other goroutines see created=false and the cached sessionID.
func TestThreadSessionRegistryConcurrentAcquireOrCreateOnSameKey(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("newThreadSessionRegistry: %v", err)
	}

	const N = 32
	var createCount int32
	var wg sync.WaitGroup
	results := make([]string, N)
	createds := make([]bool, N)
	errs := make([]error, N)
	start := make(chan struct{})
	for i := 0; i < N; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			<-start
			sid, created, err := reg.AcquireOrCreate("C1", "1700000000.000100", func() (string, error) {
				atomic.AddInt32(&createCount, 1)
				return "gc-sess-1", nil
			})
			results[idx] = sid
			createds[idx] = created
			errs[idx] = err
		}(i)
	}
	close(start)
	wg.Wait()

	if got := atomic.LoadInt32(&createCount); got != 1 {
		t.Fatalf("create callback ran %d times; want exactly 1", got)
	}
	winners := 0
	for i := 0; i < N; i++ {
		if errs[i] != nil {
			t.Errorf("goroutine %d: err=%v", i, errs[i])
		}
		if results[i] != "gc-sess-1" {
			t.Errorf("goroutine %d: sid=%q, want gc-sess-1", i, results[i])
		}
		if createds[i] {
			winners++
		}
	}
	if winners != 1 {
		t.Errorf("created=true count = %d; want exactly 1", winners)
	}
}

// TestThreadSessionRegistryRemoveThenReacquire — Remove drops the
// binding so the next AcquireOrCreate runs the create callback again
// rather than serving the stale value.
func TestThreadSessionRegistryRemoveThenReacquire(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("newThreadSessionRegistry: %v", err)
	}
	if _, _, err := reg.AcquireOrCreate("C1", "T1", func() (string, error) { return "gc-sess-1", nil }); err != nil {
		t.Fatalf("first acquire: %v", err)
	}
	if err := reg.Remove("C1", "T1"); err != nil {
		t.Fatalf("Remove: %v", err)
	}
	if _, ok := reg.Lookup("C1", "T1"); ok {
		t.Errorf("Lookup ok=true after Remove; want false")
	}
	sid, created, err := reg.AcquireOrCreate("C1", "T1", func() (string, error) { return "gc-sess-2", nil })
	if err != nil {
		t.Fatalf("second acquire: %v", err)
	}
	if !created {
		t.Errorf("created=false after Remove + reacquire; want true")
	}
	if sid != "gc-sess-2" {
		t.Errorf("sid=%q after reacquire, want gc-sess-2", sid)
	}
}

// TestThreadSessionRegistryRemoveBySessionID exercises the reverse
// index used by cby.5.4 (session.stopped subscriber): given only a
// session ID, drop the (channel, thread) binding and return the keys
// that were dropped.
func TestThreadSessionRegistryRemoveBySessionID(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("newThreadSessionRegistry: %v", err)
	}
	if _, _, err := reg.AcquireOrCreate("C1", "T1", func() (string, error) { return "gc-sess-1", nil }); err != nil {
		t.Fatalf("acquire C1/T1: %v", err)
	}
	if _, _, err := reg.AcquireOrCreate("C2", "T2", func() (string, error) { return "gc-sess-2", nil }); err != nil {
		t.Fatalf("acquire C2/T2: %v", err)
	}

	channelID, threadTS, ok := reg.RemoveBySessionID("gc-sess-1")
	if !ok {
		t.Fatal("RemoveBySessionID ok=false; want true")
	}
	if channelID != "C1" || threadTS != "T1" {
		t.Errorf("RemoveBySessionID returned (%q,%q); want (C1,T1)", channelID, threadTS)
	}
	if _, ok := reg.Lookup("C1", "T1"); ok {
		t.Errorf("C1/T1 still present after RemoveBySessionID")
	}
	if got, ok := reg.Lookup("C2", "T2"); !ok || got != "gc-sess-2" {
		t.Errorf("C2/T2 disturbed by RemoveBySessionID: got=%q ok=%v", got, ok)
	}

	// Idempotence: removing an unknown session ID is not an error.
	if _, _, ok := reg.RemoveBySessionID("gc-nonexistent"); ok {
		t.Errorf("RemoveBySessionID on unknown sid returned ok=true; want false")
	}
}

// TestThreadSessionRegistryTolerantLoadMissingFile — first-startup case:
// the registry file does not yet exist. Construction must succeed with
// an empty in-memory map.
func TestThreadSessionRegistryTolerantLoadMissingFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("missing file load: %v", err)
	}
	if _, ok := reg.Lookup("C1", "T1"); ok {
		t.Errorf("Lookup ok=true on empty registry")
	}
}

// TestThreadSessionRegistryTolerantLoadEmptyFile — operator (or a
// crashed half-write) leaves a zero-byte file. Construction must
// succeed and the in-memory state must be empty.
func TestThreadSessionRegistryTolerantLoadEmptyFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	if err := os.WriteFile(path, nil, 0o600); err != nil {
		t.Fatalf("seed empty file: %v", err)
	}
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("empty file load: %v", err)
	}
	if _, ok := reg.Lookup("C1", "T1"); ok {
		t.Errorf("Lookup ok=true on empty file")
	}
}

// TestThreadSessionRegistryTolerantLoadMalformedFile — a hand-edited
// or partially-written JSON file must not prevent the adapter from
// starting. Construction logs a warning and yields an empty registry.
func TestThreadSessionRegistryTolerantLoadMalformedFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	if err := os.WriteFile(path, []byte("{not json"), 0o600); err != nil {
		t.Fatalf("seed malformed: %v", err)
	}
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("malformed file load: err=%v; want tolerant nil error", err)
	}
	if _, ok := reg.Lookup("C1", "T1"); ok {
		t.Errorf("Lookup ok=true on malformed file")
	}
	// After a tolerant load, a fresh AcquireOrCreate must still
	// persist correctly — the registry should overwrite the corrupt
	// file on next save.
	if _, _, err := reg.AcquireOrCreate("C1", "T1", func() (string, error) { return "gc-sess-1", nil }); err != nil {
		t.Fatalf("AcquireOrCreate after malformed load: %v", err)
	}
	reg2, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("reload after recover: %v", err)
	}
	if got, ok := reg2.Lookup("C1", "T1"); !ok || got != "gc-sess-1" {
		t.Errorf("post-recover Lookup = (%q, %v); want (gc-sess-1, true)", got, ok)
	}
}

// TestThreadSessionRegistryCreateErrorDoesNotCacheFailure — if the
// create callback fails, the registry MUST NOT cache an empty value.
// The next AcquireOrCreate retries by invoking the callback again.
func TestThreadSessionRegistryCreateErrorDoesNotCacheFailure(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("newThreadSessionRegistry: %v", err)
	}
	wantErr := errors.New("spawn rejected")
	_, _, err = reg.AcquireOrCreate("C1", "T1", func() (string, error) {
		return "", wantErr
	})
	if !errors.Is(err, wantErr) {
		t.Fatalf("first acquire err = %v; want %v", err, wantErr)
	}
	if _, ok := reg.Lookup("C1", "T1"); ok {
		t.Errorf("failed create cached; Lookup ok=true after error")
	}
	// Retry succeeds and is treated as a fresh create.
	sid, created, err := reg.AcquireOrCreate("C1", "T1", func() (string, error) {
		return "gc-sess-retry", nil
	})
	if err != nil {
		t.Fatalf("retry: %v", err)
	}
	if !created {
		t.Errorf("created=false on retry; want true (failed prior create must not be cached)")
	}
	if sid != "gc-sess-retry" {
		t.Errorf("sid=%q, want gc-sess-retry", sid)
	}
}

// TestThreadSessionRegistryConcurrentDistinctKeysDoNotSerialize is a
// liveness check: concurrent AcquireOrCreate on disjoint
// (channel,thread) keys must not block each other on the per-key
// mutex. The test runs N goroutines on N distinct keys with a slow
// create callback; with proper per-key mutexing all creates run
// concurrently.
func TestThreadSessionRegistryConcurrentDistinctKeysDoNotSerialize(t *testing.T) {
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("newThreadSessionRegistry: %v", err)
	}
	const N = 8
	var wg sync.WaitGroup
	gate := make(chan struct{})
	var inFlight int32
	var maxInFlight int32
	for i := 0; i < N; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			ch := fmt.Sprintf("C%d", idx)
			ts := fmt.Sprintf("T%d", idx)
			sid, _, err := reg.AcquireOrCreate(ch, ts, func() (string, error) {
				cur := atomic.AddInt32(&inFlight, 1)
				for {
					m := atomic.LoadInt32(&maxInFlight)
					if cur <= m || atomic.CompareAndSwapInt32(&maxInFlight, m, cur) {
						break
					}
				}
				<-gate
				atomic.AddInt32(&inFlight, -1)
				return fmt.Sprintf("gc-sess-%d", idx), nil
			})
			if err != nil {
				t.Errorf("goroutine %d err=%v", idx, err)
			}
			if sid != fmt.Sprintf("gc-sess-%d", idx) {
				t.Errorf("goroutine %d sid=%q", idx, sid)
			}
		}(i)
	}
	// Wait until at least 2 goroutines are inside the create
	// callback simultaneously, then release the gate. If the
	// registry serialized distinct keys, this would deadlock and the
	// test would hang past `go test -timeout`.
	for atomic.LoadInt32(&inFlight) < 2 {
		runtime.Gosched()
	}
	close(gate)
	wg.Wait()
	if got := atomic.LoadInt32(&maxInFlight); got < 2 {
		t.Errorf("max in-flight creates = %d; want >= 2 (per-key mutex must not serialize distinct keys)", got)
	}
}
