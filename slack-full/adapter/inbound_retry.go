package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"math/rand"
	"time"
)

// inboundRetryPolicy bounds how postInbound retries
// POST /v0/city/{city}/extmsg/inbound.
//
// A 5xx or a transport error is ambiguous: gc may already have stored the
// transcript entry before the failure (a bd write that landed but reported
// an error). Dropping the message there loses it silently: nobody is woken.
// Retrying is safe because every attempt sends the same body, so the same
// provider_message_id and dedup_key, and gc's Append dedups on them: a retry
// of a stored message finds the entry, succeeds, and notifies once.
//
// A 4xx is the request's own fault and is never retried.
type inboundRetryPolicy struct {
	// maxAttempts counts the first try. 1 disables retry.
	maxAttempts int
	// baseDelay is the backoff before the first retry; it doubles per
	// retry up to maxDelay. Each delay is jittered into [d/2, d].
	baseDelay time.Duration
	maxDelay  time.Duration
	// budget caps the wall time of all attempts and sleeps together. It
	// is also each attempt's deadline, so a hung gc cannot hold the
	// dispatch slot forever.
	budget time.Duration
	// sleep waits between attempts. Nil means a real, ctx-aware sleep;
	// tests inject one that records the delays instead.
	sleep func(ctx context.Context, d time.Duration) error
}

// defaultInboundRetry is used when cfg.inboundRetry is the zero value:
// 5 attempts with delays of about 1s, 2s, 4s and 8s, inside 60s.
var defaultInboundRetry = inboundRetryPolicy{
	maxAttempts: 5,
	baseDelay:   time.Second,
	maxDelay:    16 * time.Second,
	budget:      60 * time.Second,
}

func (p inboundRetryPolicy) withDefaults() inboundRetryPolicy {
	if p.maxAttempts <= 0 {
		p.maxAttempts = defaultInboundRetry.maxAttempts
	}
	if p.baseDelay <= 0 {
		p.baseDelay = defaultInboundRetry.baseDelay
	}
	if p.maxDelay <= 0 {
		p.maxDelay = defaultInboundRetry.maxDelay
	}
	if p.budget <= 0 {
		p.budget = defaultInboundRetry.budget
	}
	if p.sleep == nil {
		p.sleep = sleepCtx
	}
	return p
}

// delay returns the jittered backoff before retry n (n=1 is the first
// retry): baseDelay*2^(n-1), capped at maxDelay, then drawn from [d/2, d].
func (p inboundRetryPolicy) delay(n int) time.Duration {
	d := p.baseDelay
	for i := 1; i < n && d < p.maxDelay; i++ {
		d *= 2
	}
	if d > p.maxDelay {
		d = p.maxDelay
	}
	half := d / 2
	return half + time.Duration(rand.Int63n(int64(d-half)+1))
}

func sleepCtx(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

// inboundStatusError is a non-2xx reply from the inbound endpoint.
type inboundStatusError struct {
	status string
	code   int
	body   string
}

func (e *inboundStatusError) Error() string { return fmt.Sprintf("%s: %s", e.status, e.body) }

// retryableInbound reports whether a failed attempt may be retried: a
// transport error or a 5xx. A 4xx is permanent.
func retryableInbound(err error) bool {
	var se *inboundStatusError
	if errors.As(err, &se) {
		return se.code >= 500
	}
	return true
}

// postInboundWithRetry runs attempt under policy p. msgID names the
// message in the retry and give-up log lines. attempt receives a context
// whose deadline is the end of the whole budget.
func postInboundWithRetry(p inboundRetryPolicy, msgID string, attempt func(ctx context.Context) error) error {
	p = p.withDefaults()
	ctx, cancel := context.WithTimeout(context.Background(), p.budget)
	defer cancel()

	var err error
	for n := 1; ; n++ {
		err = attempt(ctx)
		if err == nil {
			if n > 1 {
				log.Printf("inbound POST delivered: msg=%s on attempt %d/%d", msgID, n, p.maxAttempts)
			}
			return nil
		}
		if !retryableInbound(err) {
			return err
		}
		if n >= p.maxAttempts {
			log.Printf("inbound POST giving up: msg=%s after %d attempts: %v", msgID, n, err)
			return fmt.Errorf("gave up after %d attempts: %w", n, err)
		}
		d := p.delay(n)
		if deadline, ok := ctx.Deadline(); ok && time.Until(deadline) <= d {
			log.Printf("inbound POST giving up: msg=%s after %d attempts, %s budget spent: %v", msgID, n, p.budget, err)
			return fmt.Errorf("gave up after %d attempts (budget %s): %w", n, p.budget, err)
		}
		log.Printf("inbound POST retry: msg=%s attempt %d/%d failed, retrying in %s: %v",
			msgID, n, p.maxAttempts, d.Round(time.Millisecond), err)
		if serr := p.sleep(ctx, d); serr != nil {
			log.Printf("inbound POST giving up: msg=%s after %d attempts, %s budget spent: %v", msgID, n, p.budget, err)
			return fmt.Errorf("gave up after %d attempts (budget %s): %w", n, p.budget, err)
		}
	}
}
