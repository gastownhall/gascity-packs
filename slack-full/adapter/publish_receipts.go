package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// publishReceiptRetention keeps delivery evidence available to later readers
// for 30 days, beyond companyReceiptRetention's 7-day inbound retry window.
// This longer audit window does not extend either store's dedup semantics.
const publishReceiptRetention = 30 * 24 * time.Hour

var errInvalidPublishReceipt = errors.New("invalid publish receipt")

// publishReceiptStore is the durable delivery-evidence contract for keyed
// POST /publish calls. It lives at <GC_CITY_PATH>/.gc/slack/publish-receipts
// (or /tmp/gc-slack-adapter/publish-receipts without a city), alongside inbound
// receipts and dead letters. Full SHA-256 key digests name private JSON files;
// neither the key nor the posted text is stored, and no marker is added to Slack.
//
// GET /publish-receipt?idempotency_key=<URL-encoded caller key> on the internal
// adapter server returns the publish-to-channel terse receipt shape plus
// posted_text_sha256, posted_at, and readback. message_id is Slack's exact ts;
// thread_ts and reply_to_message_id identify a threaded post's parent. The
// digest covers the alias-rewritten UTF-8 bytes sent to chat.postMessage, not
// Slack's canonicalized readback. readback is pending until the read concludes,
// then confirmed, readback_unconfirmed, readback_unavailable, or readback_auth.
// delivered is true only after timestamp + canonicalized text verification.
//
// A receipt is written as soon as Slack accepts the post with a ts, then
// atomically updated after readback, including retry re-verification. A crash
// between these steps leaves pending evidence of acceptance, not delivery.
// Confirmed evidence cannot be downgraded by a slower read of the same post.
// Reusing a key for a newer accepted post replaces its previous receipt;
// Slack timestamps order acceptance even when HTTP responses arrive out of
// order. Neither a late acceptance nor a late readback can replace a newer ts.
//
// This store does NOT extend the in-memory dedup TTL or prevent reposts after
// restart. Receipts expire by posted_at after publishReceiptRetention (30 days),
// with an hourly/startup sweep. 404 means UNKNOWN, never undelivered: unkeyed
// posts, file uploads, older deliveries, expired receipts, and writes lost to a
// disk failure may have no receipt. A lookup or sweep removes corrupt receipts
// with one log line; the first corrupt lookup returns 404 unknown immediately.
// I/O failures (including failed cleanup) return 500 and preserve retryability.
// Persistence failures are logged and surfaced as metadata.receipt_store on
// the publish response without undoing a Slack delivery or inducing a repost.
// This evidence describes a past observation, not whether Slack still has the
// message now. It is slack-full-only; sibling packs have no such receipt store.
type publishReceiptStore struct {
	mu  sync.Mutex
	dir string
	now func() time.Time
}

type storedPublishReceipt struct {
	Delivered        bool      `json:"delivered"`
	ConversationID   string    `json:"conversation_id"`
	MessageID        string    `json:"message_id"`
	ThreadTS         string    `json:"thread_ts,omitempty"`
	ReplyToMessageID string    `json:"reply_to_message_id,omitempty"`
	FailureKind      string    `json:"failure_kind,omitempty"`
	PostedTextSHA256 string    `json:"posted_text_sha256"`
	PostedAt         time.Time `json:"posted_at"`
	Readback         string    `json:"readback"`
}

func newPublishReceiptStore(dir string) (*publishReceiptStore, error) {
	if strings.TrimSpace(dir) == "" {
		return nil, errors.New("publish receipt directory required")
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	info, err := os.Lstat(dir)
	if err != nil {
		return nil, err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return nil, fmt.Errorf("publish receipt directory %q must be a real directory", dir)
	}
	if err := os.Chmod(dir, 0o700); err != nil {
		return nil, err
	}
	if err := fsyncDir(filepath.Dir(dir)); err != nil {
		return nil, err
	}
	return &publishReceiptStore{dir: dir, now: time.Now}, nil
}

func publishReceiptDigest(value string) string {
	digest := sha256.Sum256([]byte(value))
	return hex.EncodeToString(digest[:])
}

func (s *publishReceiptStore) path(key string) string {
	return filepath.Join(s.dir, publishReceiptDigest(key)+".json")
}

func (s *publishReceiptStore) read(path string) (storedPublishReceipt, error) {
	var receipt storedPublishReceipt
	f, err := openBeneath(s.dir, filepath.Base(path))
	if err != nil {
		return receipt, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, 64*1024+1))
	if err != nil {
		return receipt, err
	}
	if len(data) > 64*1024 {
		return receipt, fmt.Errorf("%w: too large", errInvalidPublishReceipt)
	}
	if err := json.Unmarshal(data, &receipt); err != nil {
		return receipt, fmt.Errorf("%w: %v", errInvalidPublishReceipt, err)
	}
	if receipt.MessageID == "" || receipt.ConversationID == "" || receipt.PostedAt.IsZero() || len(receipt.PostedTextSHA256) != 64 || receipt.Readback == "" {
		return receipt, errInvalidPublishReceipt
	}
	return receipt, nil
}

// write uses the inbound receipt store's temp + fsync + rename discipline.
// All callers hold mu, so readers see either complete version of a receipt.
func (s *publishReceiptStore) write(path string, receipt storedPublishReceipt) error {
	data, err := json.Marshal(receipt)
	if err != nil {
		return err
	}
	f, err := os.CreateTemp(s.dir, "publish-*.tmp")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if _, err = f.Write(data); err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	if err := os.Rename(f.Name(), path); err != nil {
		return err
	}
	return fsyncDir(s.dir)
}

func (s *publishReceiptStore) RecordPosted(key string, receipt publishReceipt, post slackPostMessageReq) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if key == "" || receipt.MessageID == "" || receipt.Conversation.ConversationID == "" {
		return errors.New("publish receipt requires key, conversation and message ts")
	}
	if existing, err := s.read(s.path(key)); err == nil {
		if compareSlackTS(existing.MessageID, receipt.MessageID) > 0 {
			return nil // Slack accepted this post before the one already stored
		}
		if existing.MessageID == receipt.MessageID && existing.ConversationID == receipt.Conversation.ConversationID {
			return nil // the acceptance write never resets this post's readback
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return s.write(s.path(key), storedPublishReceipt{
		ConversationID: receipt.Conversation.ConversationID,
		MessageID:      receipt.MessageID, ThreadTS: post.ThreadTS, ReplyToMessageID: post.ThreadTS,
		PostedTextSHA256: publishReceiptDigest(post.Text), PostedAt: s.now().UTC(), Readback: "pending",
	})
}

func (s *publishReceiptStore) RecordReadback(key string, receipt publishReceipt) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	stored, err := s.read(s.path(key))
	if err != nil {
		return err
	}
	if stored.MessageID != receipt.MessageID || stored.ConversationID != receipt.Conversation.ConversationID || stored.Delivered {
		return nil // stale update, or a faster read already confirmed this post
	}
	stored.Delivered, stored.FailureKind = receipt.Delivered, receipt.FailureKind
	stored.Readback = receipt.Metadata[receiptMetadataKeyReadback]
	if receipt.Delivered {
		stored.Readback = "confirmed"
	}
	if stored.Readback == "" {
		return errors.New("publish receipt missing readback result")
	}
	return s.write(s.path(key), stored)
}

func (s *publishReceiptStore) Get(key string) (storedPublishReceipt, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, err := os.Lstat(s.dir); err != nil {
		// A missing store is an operational failure, not an unknown key.
		// Do not wrap ENOENT: the HTTP handler reserves it for missing receipts.
		return storedPublishReceipt{}, fmt.Errorf("publish receipt directory unavailable: %v", err)
	}
	path := s.path(key)
	receipt, err := s.read(path)
	if errors.Is(err, errInvalidPublishReceipt) {
		if err := os.Remove(path); err != nil {
			return storedPublishReceipt{}, fmt.Errorf("remove corrupt publish receipt: %w", err)
		}
		log.Printf("publish receipt prune: removed corrupt receipt %s", filepath.Base(path))
		if err := fsyncDir(s.dir); err != nil {
			return storedPublishReceipt{}, err
		}
		return storedPublishReceipt{}, os.ErrNotExist
	}
	if err == nil && !s.now().Before(receipt.PostedAt.Add(publishReceiptRetention)) {
		return storedPublishReceipt{}, os.ErrNotExist
	}
	return receipt, err
}

func (s *publishReceiptStore) Prune() (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	entries, err := os.ReadDir(s.dir)
	if err != nil {
		return 0, err
	}
	removed := 0
	var errs []error
	for _, entry := range entries {
		// A crash before rename leaves a private temporary copy. The mutex
		// excludes live writers; age-gating also protects recent crash evidence.
		if strings.HasPrefix(entry.Name(), "publish-") && strings.HasSuffix(entry.Name(), ".tmp") && !entry.IsDir() {
			info, err := entry.Info()
			if err != nil {
				errs = append(errs, err)
				continue
			}
			if !s.now().Before(info.ModTime().Add(publishReceiptRetention)) {
				if err := os.Remove(filepath.Join(s.dir, entry.Name())); err != nil {
					errs = append(errs, err)
				} else {
					removed++
				}
			}
			continue
		}
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}
		path := filepath.Join(s.dir, entry.Name())
		receipt, err := s.read(path)
		invalid := errors.Is(err, errInvalidPublishReceipt)
		if err != nil && !invalid {
			errs = append(errs, err)
			continue
		}
		if !invalid && s.now().Before(receipt.PostedAt.Add(publishReceiptRetention)) {
			continue
		}
		if err := os.Remove(path); err != nil {
			errs = append(errs, err)
		} else {
			removed++
			if invalid {
				log.Printf("publish receipt prune: removed corrupt receipt %s", entry.Name())
			}
		}
	}
	if removed > 0 {
		errs = append(errs, fsyncDir(s.dir))
	}
	return removed, errors.Join(errs...)
}

func (s *publishReceiptStore) runJanitor(ctx context.Context) {
	ticker := time.NewTicker(time.Hour)
	defer ticker.Stop()
	for {
		if _, err := s.Prune(); err != nil {
			log.Printf("publish receipt prune: %v", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func publishReceiptStoreError(receipt *publishReceipt, err error) {
	if err == nil {
		return
	}
	log.Printf("publish receipt persistence failed: conv=%s ts=%s: %v", receipt.Conversation.ConversationID, receipt.MessageID, err)
	// Cached receipts and in-flight encoders may still own the old map.
	metadata := make(map[string]string, len(receipt.Metadata)+1)
	for key, value := range receipt.Metadata {
		metadata[key] = value
	}
	receipt.Metadata = metadata
	receipt.Metadata["receipt_store"] = "unavailable"
}

func (s *publishReceiptStore) recordPosted(key string, receipt *publishReceipt, post slackPostMessageReq) {
	if s != nil && key != "" && receipt.MessageID != "" {
		publishReceiptStoreError(receipt, s.RecordPosted(key, *receipt, post))
	}
}

func (s *publishReceiptStore) recordReadback(key string, receipt *publishReceipt) {
	if s != nil && key != "" && receipt.MessageID != "" {
		publishReceiptStoreError(receipt, s.RecordReadback(key, *receipt))
	}
}

func handlePublishReceipt(store *publishReceiptStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		key := r.URL.Query().Get("idempotency_key")
		if key == "" {
			http.Error(w, "idempotency_key required", http.StatusBadRequest)
			return
		}
		receipt, err := store.Get(key)
		if errors.Is(err, os.ErrNotExist) {
			http.Error(w, "receipt unknown (not evidence of non-delivery)", http.StatusNotFound)
			return
		}
		if err != nil {
			log.Printf("publish receipt lookup: %v", err)
			http.Error(w, "receipt lookup failed", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(receipt)
	}
}
