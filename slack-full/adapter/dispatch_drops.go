package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync/atomic"
	"time"
)

// dispatchDroppedTotal counts inbound Slack deliveries dropped because
// the dispatch semaphore was saturated (acquireDispatchSlot returned
// not-ok). Package-level like dispatchInflightWG: saturation is a
// process-wide signal no matter which cfg value observed it. Exposed
// on /healthz and rolled up by runDispatchDropSummary so operators
// can see loss without scraping per-event "dispatch queue full" lines.
var dispatchDroppedTotal atomic.Uint64

// handleHealthz reports liveness plus the cumulative dropped-dispatch
// count. The first line stays exactly "ok" so status-code and
// grep-based checks keep working; the counter rides on a second line.
// When a company gateway is wired (production main() only), its barrier
// state, receipt-store write-failure counter, and snapshot state ride
// on trailing lines — the sole status surface for the company path
// (there is no separate gateway status payload; see company_delivery.go).
func handleHealthz(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = fmt.Fprintf(w, "ok\ndispatch_dropped_total=%d\n", dispatchDroppedTotal.Load())
	_, _ = io.WriteString(w, socketModeHealthzDetail())
	if gw := companyHealthStatus.Load(); gw != nil {
		_, _ = io.WriteString(w, gw.healthzDetail())
	}
}

// dispatchDropSummaryInterval paces the saturation roll-up log. One
// minute keeps the signal near-real-time; ticks with no new drops log
// nothing, so a healthy adapter stays silent.
const dispatchDropSummaryInterval = time.Minute

// runDispatchDropSummary logs a periodic roll-up of dropped
// dispatches so sustained saturation shows up as a low-noise
// heartbeat even when per-event drop lines are flooding. Only ticks
// where new drops occurred produce a line.
func runDispatchDropSummary(ctx context.Context, interval time.Duration, capacity int) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	var lastReported uint64
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			total := dispatchDroppedTotal.Load()
			if delta := total - lastReported; delta > 0 {
				log.Printf("slack adapter: dispatch saturation summary: dropped=%d in last %s (total=%d cap=%d)",
					delta, interval, total, capacity)
				lastReported = total
			}
		}
	}
}
