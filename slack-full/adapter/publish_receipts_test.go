package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func testPublishReceiptStore(t *testing.T, dir string) *publishReceiptStore {
	t.Helper()
	store, err := newPublishReceiptStore(dir)
	if err != nil {
		t.Fatal(err)
	}
	return store
}

func TestPublishReceiptSurvivesRestartAndReadbackUpdates(t *testing.T) {
	dir := t.TempDir()
	store := testPublishReceiptStore(t, dir)
	postedAt := time.Now().UTC().Truncate(time.Second)
	store.now = func() time.Time { return postedAt }
	key := "../../caller key?&="
	receipt := publishReceipt{Conversation: conversationRef{ConversationID: "C1"}, MessageID: "1700.002"}
	post := slackPostMessageReq{Text: "hello", ThreadTS: "1700.001"}
	if err := store.RecordPosted(key, receipt, post); err != nil {
		t.Fatal(err)
	}
	store = testPublishReceiptStore(t, dir) // simulate a crash before readback
	got, err := store.Get(key)
	if err != nil {
		t.Fatal(err)
	}
	if got.Delivered || got.Readback != "pending" || got.ConversationID != "C1" || got.MessageID != "1700.002" || got.ThreadTS != "1700.001" || got.ReplyToMessageID != got.ThreadTS || !got.PostedAt.Equal(postedAt) {
		t.Fatalf("pending receipt = %+v", got)
	}
	if got.PostedTextSHA256 != "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824" {
		t.Fatalf("posted text digest = %q", got.PostedTextSHA256)
	}
	files, err := os.ReadDir(dir)
	if err != nil || len(files) != 1 || len(files[0].Name()) != 64+len(".json") {
		t.Fatalf("private digest-keyed files = %v, %v", files, err)
	}
	info, err := os.Stat(filepath.Join(dir, files[0].Name()))
	if err != nil || info.Mode().Perm() != 0o600 {
		t.Fatalf("receipt file permissions: %v, %v", info, err)
	}
	receipt.Delivered = true
	if err := store.RecordReadback(key, receipt); err != nil {
		t.Fatal(err)
	}
	store = testPublishReceiptStore(t, dir)
	got, err = store.Get(key)
	if err != nil || !got.Delivered || got.Readback != "confirmed" || !got.PostedAt.Equal(postedAt) {
		t.Fatalf("confirmed receipt after restart = %+v, %v", got, err)
	}
	// A slow failed read cannot downgrade proof, nor overwrite a newer post.
	receipt.Delivered = false
	receipt.FailureKind = "transient"
	receipt.Metadata = map[string]string{receiptMetadataKeyReadback: slackReadbackUnavailable}
	if err := store.RecordReadback(key, receipt); err != nil {
		t.Fatal(err)
	}
	got, err = store.Get(key)
	if err != nil || !got.Delivered {
		t.Fatalf("slow read downgraded confirmation: %+v, %v", got, err)
	}
	newPost := receipt
	newPost.MessageID = "1700.003"
	if err := store.RecordPosted(key, newPost, slackPostMessageReq{Text: "next"}); err != nil {
		t.Fatal(err)
	}
	if err := store.RecordReadback(key, receipt); err != nil {
		t.Fatal(err)
	}
	got, err = store.Get(key)
	if err != nil || got.MessageID != "1700.003" || got.Readback != "pending" {
		t.Fatalf("stale read changed replacement: %+v, %v", got, err)
	}
	// Slack can return the older post's acceptance response last, after the
	// newer receipt is already confirmed. It must not roll evidence backward.
	newPost.Delivered = true
	if err := store.RecordReadback(key, newPost); err != nil {
		t.Fatal(err)
	}
	if err := store.RecordPosted(key, receipt, post); err != nil {
		t.Fatal(err)
	}
	got, err = store.Get(key)
	if err != nil || got.MessageID != "1700.003" || !got.Delivered {
		t.Fatalf("late acceptance replaced newer confirmation: %+v, %v", got, err)
	}
}

func TestPublishReceiptPruneByPostedAge(t *testing.T) {
	store := testPublishReceiptStore(t, t.TempDir())
	now := time.Now().UTC()
	store.now = func() time.Time { return now.Add(-31 * 24 * time.Hour) }
	receipt := publishReceipt{Conversation: conversationRef{ConversationID: "C1"}, MessageID: "1.2"}
	if err := store.RecordPosted("old", receipt, slackPostMessageReq{Text: "old"}); err != nil {
		t.Fatal(err)
	}
	store.now = func() time.Time { return now }
	if err := store.RecordPosted("fresh", receipt, slackPostMessageReq{Text: "fresh"}); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Get("old"); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("expired lookup = %v, want unknown before sweep", err)
	}
	removed, err := store.Prune()
	if err != nil || removed != 1 {
		t.Fatalf("Prune = %d, %v", removed, err)
	}
	if _, err := os.Stat(store.path("old")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("old receipt file remains: %v", err)
	}
	if _, err := store.Get("fresh"); err != nil {
		t.Fatalf("fresh receipt lost: %v", err)
	}
}

func TestPublishReceiptPrunesCorruptFiles(t *testing.T) {
	for _, tc := range []struct{ name, data string }{
		{"truncated", `{"message_id":`},
		{"invalid fields", `{}`},
		{"oversized", strings.Repeat(" ", 64*1024+1)},
	} {
		t.Run(tc.name, func(t *testing.T) {
			store := testPublishReceiptStore(t, t.TempDir())
			receipt := publishReceipt{Conversation: conversationRef{ConversationID: "C1"}, MessageID: "1.2"}
			if err := store.RecordPosted("fresh", receipt, slackPostMessageReq{Text: "fresh"}); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(store.path("corrupt"), []byte(tc.data), 0o600); err != nil {
				t.Fatal(err)
			}
			var logs bytes.Buffer
			previousLogOutput := log.Writer()
			log.SetOutput(&logs)
			t.Cleanup(func() { log.SetOutput(previousLogOutput) })
			w := httptest.NewRecorder()
			handlePublishReceipt(store)(w, httptest.NewRequest(http.MethodGet, "/publish-receipt?idempotency_key=corrupt", nil))
			if w.Code != http.StatusNotFound {
				t.Fatalf("first corrupt lookup = %d: %s", w.Code, w.Body)
			}
			if _, err := os.Stat(store.path("corrupt")); !errors.Is(err, os.ErrNotExist) {
				t.Fatalf("corrupt file remains: %v", err)
			}
			if _, err := store.Get("corrupt"); !errors.Is(err, os.ErrNotExist) {
				t.Fatalf("second corrupt lookup = %v", err)
			}
			if got := strings.Count(logs.String(), "removed corrupt receipt "+filepath.Base(store.path("corrupt"))); got != 1 {
				t.Fatalf("corrupt lookup logged %d removals, want one: %s", got, &logs)
			}
			if err := os.WriteFile(store.path("sweep-corrupt"), []byte(tc.data), 0o600); err != nil {
				t.Fatal(err)
			}
			if removed, err := store.Prune(); err != nil || removed != 1 {
				t.Fatalf("sweep cleanup = %d, %v", removed, err)
			}
			if removed, err := store.Prune(); err != nil || removed != 0 {
				t.Fatalf("second cleanup = %d, %v", removed, err)
			}
			if _, err := store.Get("fresh"); err != nil {
				t.Fatalf("fresh receipt lost: %v", err)
			}
		})
	}
}

func TestPublishReceiptGET(t *testing.T) {
	store := testPublishReceiptStore(t, t.TempDir())
	key := "key with ?&=/ reserved characters"
	receipt := publishReceipt{Conversation: conversationRef{ConversationID: "C1"}, MessageID: "1.2"}
	if err := store.RecordPosted(key, receipt, slackPostMessageReq{Text: "hello", ThreadTS: "1.1"}); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(store.path("corrupt"), []byte("{bad"), 0o600); err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		key, method string
		status      int
	}{
		{key, http.MethodGet, http.StatusOK},
		{"unknown", http.MethodGet, http.StatusNotFound},
		{"", http.MethodGet, http.StatusBadRequest},
		{"corrupt", http.MethodGet, http.StatusNotFound},
		{key, http.MethodPost, http.StatusMethodNotAllowed},
	} {
		t.Run(test.key+test.method, func(t *testing.T) {
			r := httptest.NewRequest(test.method, "/publish-receipt?idempotency_key="+url.QueryEscape(test.key), nil)
			w := httptest.NewRecorder()
			handlePublishReceipt(store)(w, r)
			if w.Code != test.status {
				t.Fatalf("status = %d, want %d: %s", w.Code, test.status, w.Body)
			}
			if w.Header().Get("Cache-Control") != "no-store" {
				t.Fatal("receipt lookup can be cached across pending/confirmed transitions")
			}
			if test.status == http.StatusOK {
				var got map[string]any
				if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
					t.Fatal(err)
				}
				if got["delivered"] != false || got["conversation_id"] != "C1" || got["message_id"] != "1.2" || got["thread_ts"] != "1.1" || got["reply_to_message_id"] != "1.1" || got["readback"] != "pending" {
					t.Fatalf("flat receipt shape = %v", got)
				}
			}
		})
	}
}

func TestPublishReceiptUnavailableStoreIsNotUnknown(t *testing.T) {
	store := testPublishReceiptStore(t, filepath.Join(t.TempDir(), "receipts"))
	if err := os.Remove(store.dir); err != nil {
		t.Fatal(err)
	}
	w := httptest.NewRecorder()
	handlePublishReceipt(store)(w, httptest.NewRequest(http.MethodGet, "/publish-receipt?idempotency_key=key", nil))
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("missing store returned %d: %s", w.Code, w.Body)
	}
}

func TestPublishReceiptPrunesOnlyAgedCrashTemporaryFiles(t *testing.T) {
	store := testPublishReceiptStore(t, t.TempDir())
	old := filepath.Join(store.dir, "publish-crashed.tmp")
	fresh := filepath.Join(store.dir, "publish-recent.tmp")
	for _, path := range []string{old, fresh} {
		if err := os.WriteFile(path, []byte("partial receipt"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	aged := time.Now().Add(-31 * 24 * time.Hour)
	if err := os.Chtimes(old, aged, aged); err != nil {
		t.Fatal(err)
	}
	removed, err := store.Prune()
	if err != nil || removed != 1 {
		t.Fatalf("temporary cleanup = %d, %v", removed, err)
	}
	if _, err := os.Stat(old); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("old crash file remains: %v", err)
	}
	if _, err := os.Stat(fresh); err != nil {
		t.Fatalf("recent temporary file was removed: %v", err)
	}
}

func TestPublishReceiptRefusesSymlinks(t *testing.T) {
	dir := t.TempDir()
	link := filepath.Join(t.TempDir(), "store")
	if err := os.Symlink(dir, link); err != nil {
		t.Fatal(err)
	}
	if _, err := newPublishReceiptStore(link); err == nil {
		t.Fatal("opened symlinked store")
	}
	store := testPublishReceiptStore(t, dir)
	if err := os.Symlink(filepath.Join(t.TempDir(), "outside"), store.path("link")); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Get("link"); err == nil || errors.Is(err, os.ErrNotExist) {
		t.Fatalf("symlink lookup = %v, want a storage error", err)
	}
	if removed, err := store.Prune(); err == nil || removed != 0 {
		t.Fatalf("unsafe-path cleanup = %d, %v, want preserved file and error", removed, err)
	}
	if _, err := os.Lstat(store.path("link")); err != nil {
		t.Fatalf("unreadable receipt path was removed: %v", err)
	}
}

func TestHandlePublishPersistsAcceptanceBeforeReadbackAndRetry(t *testing.T) {
	fastReadbackTimings(t)
	store := testPublishReceiptStore(t, t.TempDir())
	const key = "integration-key"
	const posted = "hello <@U123> & welcome"
	var captured slackPostMessageReq
	posts := 0
	readable := false
	original := slackAPIBase
	t.Cleanup(func() { slackAPIBase = original })
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.URL.Path == "/chat.postMessage" {
			posts++
			if err := json.NewDecoder(r.Body).Decode(&captured); err != nil {
				t.Error(err)
			}
			_, _ = w.Write([]byte(`{"ok":true,"ts":"1700.002"}`))
			return
		}
		if r.URL.Path != "/conversations.replies" || r.URL.Query().Get("ts") != "1700.001" {
			t.Errorf("readback request = %s", r.URL)
		}
		got, err := store.Get(key)
		if err != nil || got.MessageID != "1700.002" || got.PostedTextSHA256 != publishReceiptDigest(posted) {
			t.Errorf("readback began before persisted acceptance: %+v, %v", got, err)
		}
		if !readable {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "messages": []map[string]string{{"ts": "1700.002", "text": slackCanonicalizeForTest(posted)}}})
	}))
	defer server.Close()
	slackAPIBase = server.URL
	cfg := config{slackBotToken: "xoxb-test", publishReceipts: store}
	aliases := &userAliasMap{byHandle: map[string]string{"bob": "<@U123>"}}
	handler := handlePublish(cfg, nil, aliases, newPublishDedupCache(publishDedupTTL))
	body := `{"session_id":"s1","conversation":{"conversation_id":"C1"},"reply_to_message_id":"1700.001","text":"hello @bob & welcome","idempotency_key":"integration-key"}`
	for _, confirmed := range []bool{false, true} {
		readable = confirmed
		if confirmed {
			// Simulate a SIGHUP alias reload between acceptance and retry. The
			// retry must verify the original U123 text, not repost with U456.
			aliases.mu.Lock()
			aliases.byHandle["bob"] = "<@U456>"
			aliases.mu.Unlock()
		}
		w := httptest.NewRecorder()
		handler(w, httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(body)))
		var receipt publishReceipt
		if err := json.Unmarshal(w.Body.Bytes(), &receipt); err != nil {
			t.Fatal(err)
		}
		if receipt.Delivered != confirmed || captured.Text != posted || posts != 1 {
			t.Fatalf("receipt=%+v text=%q posts=%d", receipt, captured.Text, posts)
		}
		reopened := testPublishReceiptStore(t, store.dir)
		got, err := reopened.Get(key)
		wantState := slackReadbackUnavailable
		if confirmed {
			wantState = "confirmed"
		}
		if err != nil || got.Delivered != confirmed || got.Readback != wantState || got.FailureKind != receipt.FailureKind {
			t.Fatalf("persisted readback = %+v, %v", got, err)
		}
	}
}

func TestHandlePublishPersistenceFailureDoesNotRepost(t *testing.T) {
	store := testPublishReceiptStore(t, filepath.Join(t.TempDir(), "receipts"))
	if err := os.Remove(store.dir); err != nil {
		t.Fatal(err)
	}
	original := slackAPIBase
	t.Cleanup(func() { slackAPIBase = original })
	var captured slackPostMessageReq
	posts := 0
	server := httptest.NewServer(newFakeSlackPublishHandler(t, &captured, "1.2", func() { posts++ }))
	defer server.Close()
	slackAPIBase = server.URL
	handler := handlePublish(config{slackBotToken: "xoxb-test", publishReceipts: store}, nil, nil, newPublishDedupCache(publishDedupTTL))
	for range 2 {
		w := httptest.NewRecorder()
		handler(w, httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(`{"session_id":"s1","conversation":{"conversation_id":"C1"},"text":"hello","idempotency_key":"disk-failure"}`)))
		var receipt publishReceipt
		if err := json.Unmarshal(w.Body.Bytes(), &receipt); err != nil {
			t.Fatal(err)
		}
		if !receipt.Delivered || receipt.Metadata["receipt_store"] != "unavailable" || posts != 1 {
			t.Fatalf("disk failure receipt=%+v posts=%d", receipt, posts)
		}
	}
}

func TestHandlePublishPersistenceFailureConcurrentReplays(t *testing.T) {
	for _, confirmed := range []bool{true, false} {
		name := "confirmed"
		if !confirmed {
			name = "readback unavailable"
		}
		t.Run(name, func(t *testing.T) {
			store := testPublishReceiptStore(t, filepath.Join(t.TempDir(), "receipts"))
			if err := os.Remove(store.dir); err != nil {
				t.Fatal(err)
			}
			original := slackAPIBase
			t.Cleanup(func() { slackAPIBase = original })
			var captured slackPostMessageReq
			var posts atomic.Int32
			fake := newFakeSlackPublishHandler(t, &captured, "1.2", func() { posts.Add(1) })
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if !confirmed && r.URL.Path != "/chat.postMessage" {
					w.WriteHeader(http.StatusServiceUnavailable)
					return
				}
				fake.ServeHTTP(w, r)
			}))
			defer server.Close()
			slackAPIBase = server.URL
			handler := handlePublish(config{slackBotToken: "xoxb-test", publishReceipts: store}, nil, nil, newPublishDedupCache(publishDedupTTL))
			publish := func() {
				w := httptest.NewRecorder()
				handler(w, httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(`{"session_id":"s1","conversation":{"conversation_id":"C1"},"text":"hello","idempotency_key":"concurrent-disk-failure"}`)))
				var receipt publishReceipt
				if err := json.Unmarshal(w.Body.Bytes(), &receipt); err != nil {
					t.Error(err)
					return
				}
				if receipt.Delivered != confirmed || receipt.MessageID != "1.2" || receipt.Metadata["receipt_store"] != "unavailable" {
					t.Errorf("disk failure receipt=%+v", receipt)
				}
			}
			publish() // Seed one accepted post before the concurrent retries.
			start := make(chan struct{})
			var wg sync.WaitGroup
			for range 16 {
				wg.Go(func() {
					<-start
					publish()
				})
			}
			close(start)
			wg.Wait()
			if got := posts.Load(); got != 1 {
				t.Fatalf("concurrent retries posted %d messages, want 1", got)
			}
		})
	}
}
