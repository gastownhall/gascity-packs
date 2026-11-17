package main

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// signingKeys is a fake Microsoft: an OpenID configuration document, a JWKS,
// and the private keys to sign tokens the JWKS will verify.
type signingKeys struct {
	srv     *httptest.Server
	keys    map[string]*rsa.PrivateKey
	fetches atomic.Int32
	// publish controls which kids the JWKS currently advertises, so a test
	// can roll keys.
	publish atomic.Pointer[[]string]
}

func newSigningKeys(t *testing.T, kids ...string) *signingKeys {
	t.Helper()
	s := &signingKeys{keys: map[string]*rsa.PrivateKey{}}
	for _, kid := range kids {
		k, err := rsa.GenerateKey(rand.Reader, 2048)
		if err != nil {
			t.Fatal(err)
		}
		s.keys[kid] = k
	}
	s.setPublished(kids...)
	mux := http.NewServeMux()
	mux.HandleFunc("/openid", func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]string{"jwks_uri": s.srv.URL + "/keys"})
	})
	mux.HandleFunc("/keys", func(w http.ResponseWriter, _ *http.Request) {
		s.fetches.Add(1)
		var out jwks
		for _, kid := range *s.publish.Load() {
			pub := s.keys[kid].PublicKey
			out.Keys = append(out.Keys, jwk{
				Kty: "RSA", Kid: kid, Use: "sig",
				N: base64.RawURLEncoding.EncodeToString(pub.N.Bytes()),
				E: base64.RawURLEncoding.EncodeToString(big.NewInt(int64(pub.E)).Bytes()),
			})
		}
		_ = json.NewEncoder(w).Encode(out)
	})
	s.srv = httptest.NewServer(mux)
	t.Cleanup(s.srv.Close)
	return s
}

func (s *signingKeys) setPublished(kids ...string) { s.publish.Store(&kids) }

func (s *signingKeys) openIDURL() string { return s.srv.URL + "/openid" }

// token signs claims with the named key. alg and kid are taken as given so
// tests can produce deliberately wrong headers.
func (s *signingKeys) token(t *testing.T, kid, alg string, claims map[string]any) string {
	t.Helper()
	hdr, _ := json.Marshal(map[string]string{"alg": alg, "typ": "JWT", "kid": kid})
	body, _ := json.Marshal(claims)
	signingInput := base64.RawURLEncoding.EncodeToString(hdr) + "." + base64.RawURLEncoding.EncodeToString(body)
	key, ok := s.keys[kid]
	if !ok {
		// Sign with a throwaway key: the token is structurally fine but
		// unverifiable, which is the "unknown kid" case.
		var err error
		key, err = rsa.GenerateKey(rand.Reader, 2048)
		if err != nil {
			t.Fatal(err)
		}
	}
	digest := sha256.Sum256([]byte(signingInput))
	sig, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, digest[:])
	if err != nil {
		t.Fatal(err)
	}
	return signingInput + "." + base64.RawURLEncoding.EncodeToString(sig)
}

func goodClaims(now time.Time) map[string]any {
	return map[string]any{
		"iss":        botFrameworkIssuer,
		"aud":        "app-1",
		"serviceurl": "https://smba.trafficmanager.net/emea/",
		"nbf":        now.Add(-time.Minute).Unix(),
		"exp":        now.Add(10 * time.Minute).Unix(),
	}
}

func TestTokenVerifier(t *testing.T) {
	ms := newSigningKeys(t, "k1")
	now := time.Now()
	v := newTokenVerifier(ms.openIDURL(), "app-1")
	v.now = func() time.Time { return now }
	ctx := context.Background()

	t.Run("valid token", func(t *testing.T) {
		claims, err := v.verify(ctx, "Bearer "+ms.token(t, "k1", "RS256", goodClaims(now)))
		if err != nil {
			t.Fatal(err)
		}
		if claims.ServiceURL != "https://smba.trafficmanager.net/emea/" || claims.Audience != "app-1" {
			t.Fatalf("claims = %+v", claims)
		}
	})

	t.Run("bearer prefix is case-insensitive", func(t *testing.T) {
		if _, err := v.verify(ctx, "bearer "+ms.token(t, "k1", "RS256", goodClaims(now))); err != nil {
			t.Fatal(err)
		}
	})

	t.Run("audience is case-insensitive", func(t *testing.T) {
		c := goodClaims(now)
		c["aud"] = "APP-1"
		if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k1", "RS256", c)); err != nil {
			t.Fatal(err)
		}
	})

	bad := []struct {
		name string
		auth func() string
		want string
	}{
		{"no header", func() string { return "" }, "missing bearer"},
		{"not bearer", func() string { return "Basic abc" }, "missing bearer"},
		{"two segments", func() string { return "Bearer a.b" }, "malformed"},
		{"garbage header segment", func() string { return "Bearer !!!.b.c" }, "decode header"},
		{"alg none", func() string {
			hdr := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"none","kid":"k1"}`))
			body := base64.RawURLEncoding.EncodeToString([]byte(`{}`))
			return "Bearer " + hdr + "." + body + "."
		}, "unsupported alg"},
		{"alg HS256", func() string { return "Bearer " + ms.token(t, "k1", "HS256", goodClaims(now)) }, "unsupported alg"},
		{"no kid", func() string { return "Bearer " + ms.token(t, "", "RS256", goodClaims(now)) }, "no kid"},
		{"unknown kid", func() string { return "Bearer " + ms.token(t, "nope", "RS256", goodClaims(now)) }, "unknown signing key"},
		{"wrong issuer", func() string {
			c := goodClaims(now)
			c["iss"] = "https://evil.example"
			return "Bearer " + ms.token(t, "k1", "RS256", c)
		}, "issuer"},
		{"wrong audience", func() string {
			c := goodClaims(now)
			c["aud"] = "someone-else"
			return "Bearer " + ms.token(t, "k1", "RS256", c)
		}, "audience"},
		{"expired", func() string {
			c := goodClaims(now)
			c["exp"] = now.Add(-10 * time.Minute).Unix()
			return "Bearer " + ms.token(t, "k1", "RS256", c)
		}, "expired"},
		{"missing exp", func() string {
			c := goodClaims(now)
			delete(c, "exp")
			return "Bearer " + ms.token(t, "k1", "RS256", c)
		}, "expired"},
		{"not yet valid", func() string {
			c := goodClaims(now)
			c["nbf"] = now.Add(10 * time.Minute).Unix()
			return "Bearer " + ms.token(t, "k1", "RS256", c)
		}, "not yet valid"},
		{"tampered claims", func() string {
			tok := ms.token(t, "k1", "RS256", goodClaims(now))
			parts := strings.Split(tok, ".")
			forged, _ := json.Marshal(map[string]any{"iss": botFrameworkIssuer, "aud": "app-1", "exp": now.Add(time.Hour).Unix()})
			parts[1] = base64.RawURLEncoding.EncodeToString(forged)
			return "Bearer " + strings.Join(parts, ".")
		}, "bad signature"},
	}
	for _, tc := range bad {
		t.Run("rejects "+tc.name, func(t *testing.T) {
			_, err := v.verify(ctx, tc.auth())
			if err == nil {
				t.Fatal("verified, want error")
			}
			if !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("error %q does not mention %q", err, tc.want)
			}
		})
	}

	t.Run("clock skew is tolerated", func(t *testing.T) {
		c := goodClaims(now)
		c["exp"] = now.Add(-2 * time.Minute).Unix() // inside the 5-minute allowance
		c["nbf"] = now.Add(2 * time.Minute).Unix()
		if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k1", "RS256", c)); err != nil {
			t.Fatal(err)
		}
	})
}

func TestTokenVerifierKeyRollover(t *testing.T) {
	ms := newSigningKeys(t, "k1", "k2")
	ms.setPublished("k1")
	now := time.Now()
	v := newTokenVerifier(ms.openIDURL(), "app-1")
	v.now = func() time.Time { return now }
	ctx := context.Background()

	if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k1", "RS256", goodClaims(now))); err != nil {
		t.Fatal(err)
	}
	if ms.fetches.Load() != 1 {
		t.Fatalf("fetches = %d, want 1", ms.fetches.Load())
	}

	// k2 is not yet published: the unknown kid triggers one early refresh,
	// which still does not find it.
	if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k2", "RS256", goodClaims(now))); err == nil {
		t.Fatal("k2 verified before it was published")
	}
	if ms.fetches.Load() != 2 {
		t.Fatalf("fetches = %d, want 2 (one early refresh)", ms.fetches.Load())
	}

	// A second unknown-kid token inside the rate-limit window must NOT
	// fetch again.
	if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k2", "RS256", goodClaims(now))); err == nil {
		t.Fatal("k2 verified before it was published")
	}
	if ms.fetches.Load() != 2 {
		t.Fatalf("fetches = %d, want 2 (refresh rate-limited)", ms.fetches.Load())
	}

	// Microsoft rolls to k2. Once the rate-limit window passes, the next
	// unknown-kid token refreshes and verifies.
	ms.setPublished("k1", "k2")
	now = now.Add(jwksUnknownKidRefreshMin + time.Second)
	if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k2", "RS256", goodClaims(now))); err != nil {
		t.Fatal(err)
	}
	if ms.fetches.Load() != 3 {
		t.Fatalf("fetches = %d, want 3", ms.fetches.Load())
	}

	// After the TTL the set is refreshed even for a known kid.
	now = now.Add(jwksTTL + time.Second)
	if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k1", "RS256", goodClaims(now))); err != nil {
		t.Fatal(err)
	}
	if ms.fetches.Load() != 4 {
		t.Fatalf("fetches = %d, want 4 (TTL refresh)", ms.fetches.Load())
	}
}

func TestTokenVerifierSurvivesFetchFailure(t *testing.T) {
	ms := newSigningKeys(t, "k1")
	now := time.Now()
	v := newTokenVerifier(ms.openIDURL(), "app-1")
	v.now = func() time.Time { return now }
	ctx := context.Background()
	if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k1", "RS256", goodClaims(now))); err != nil {
		t.Fatal(err)
	}
	// Microsoft goes away; the cached key keeps verifying past the TTL.
	ms.srv.Close()
	now = now.Add(jwksTTL + time.Second)
	if _, err := v.verify(ctx, "Bearer "+ms.token(t, "k1", "RS256", goodClaims(now))); err != nil {
		t.Fatalf("cached key should still verify when refresh fails: %v", err)
	}
}

func TestHandleActivitiesEndToEnd(t *testing.T) {
	ms := newSigningKeys(t, "k1")
	gc := newCaptureGC(t)
	cfg := testConfig(gc.srv.URL)
	v := newTokenVerifier(ms.openIDURL(), cfg.appID)
	convs := newConversationTable("")
	h := handleActivities(cfg, v, convs)
	now := time.Now()

	post := func(auth string, act activity) int {
		body, _ := json.Marshal(act)
		req := httptest.NewRequest(http.MethodPost, "/api/messages", strings.NewReader(string(body)))
		req.Header.Set("Authorization", auth)
		rec := httptest.NewRecorder()
		h(rec, req)
		return rec.Code
	}

	if code := post("Bearer "+ms.token(t, "k1", "RS256", goodClaims(now)), channelMention("<at>gc</at> hello")); code != http.StatusOK {
		t.Fatalf("valid request: status %d", code)
	}
	if got := gc.wait(t); got.Text != "hello" {
		t.Fatalf("bridged text = %q", got.Text)
	}

	// Token minted for one regional service, activity pointing replies at
	// another: refused before anything is bridged.
	act := channelMention("<at>gc</at> hello")
	act.ServiceURL = "https://attacker.example/"
	if code := post("Bearer "+ms.token(t, "k1", "RS256", goodClaims(now)), act); code != http.StatusUnauthorized {
		t.Fatalf("serviceUrl mismatch: status %d, want 401", code)
	}
	if _, ok := convs.lookup(act.Conversation.ID, ""); ok && gc.count() != 1 {
		t.Fatal("mismatched activity must not be bridged")
	}
}
