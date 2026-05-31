package main

import (
	"io"
	"log"
	"net/http"
)

// handleInteractions acks Slack interactive payloads (block buttons, modal
// submits). Tier 2 does no custom interaction handling — it verifies the
// signature and returns 200 so Slack dismisses the interaction without
// retrying. Custom modal flows are Tier 3.
//
// Interactive payloads arrive as application/x-www-form-urlencoded with a
// `payload` field; the Slack signature is computed over the raw request
// body, so we verify the bytes as-read before doing anything else.
func (s *server) handleInteractions() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		body, err := io.ReadAll(io.LimitReader(r.Body, maxInboundBody))
		if err != nil {
			http.Error(w, "read body", http.StatusBadRequest)
			return
		}
		ts := r.Header.Get("X-Slack-Request-Timestamp")
		sig := r.Header.Get("X-Slack-Signature")
		if !verifySlackSignature(s.cfg.signingSecret, ts, body, sig) {
			log.Printf("slack interaction signature verify FAILED")
			http.Error(w, "invalid signature", http.StatusUnauthorized)
			return
		}
		log.Printf("interaction acked (%d bytes)", len(body))
		w.WriteHeader(http.StatusOK)
	}
}
