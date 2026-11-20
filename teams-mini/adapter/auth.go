// Bot Framework inbound authentication.
//
// Every request the Bot Framework sends to a bot's messaging endpoint
// carries `Authorization: Bearer <JWT>`. The token is signed by Microsoft
// with a key published in the JWKS named by the Bot Framework's OpenID
// configuration document. A bot proves a request is genuine by checking:
//
//  1. the signature, against the key whose `kid` the token header names;
//  2. the issuer, which must be the Bot Framework;
//  3. the audience, which must be this bot's app id;
//  4. the validity window (`nbf`/`exp`), with a small clock-skew allowance;
//  5. the `serviceurl` claim against the activity's serviceUrl (done by the
//     caller, which has the activity).
//
// This is the Bot Framework's documented model
// (https://learn.microsoft.com/azure/bot-service/rest-api/bot-framework-rest-connector-authentication)
// and is the whole trust boundary on the inbound path: there is no shared
// signing secret as with Slack. Implemented against the standard library
// only (RS256 is RSA PKCS#1 v1.5 over SHA-256) so the pack carries no
// third-party dependency.
//
// Keys are cached for a day and refreshed early when a token names a `kid`
// the cache does not hold, which is how Microsoft rolls keys; refreshes on
// an unknown kid are rate-limited so a flood of bogus tokens cannot turn
// the adapter into a JWKS-fetching loop.
package main

import (
	"context"
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"strings"
	"sync"
	"time"
)

const (
	// botFrameworkIssuer is the only issuer accepted for inbound tokens.
	botFrameworkIssuer = "https://api.botframework.com"

	// jwtClockSkew is the allowance applied to nbf and exp.
	jwtClockSkew = 5 * time.Minute

	// jwksTTL is how long a fetched key set is trusted before it is
	// refreshed on the next verification.
	jwksTTL = 24 * time.Hour

	// jwksUnknownKidRefreshMin rate-limits the early refresh an unknown kid
	// triggers.
	jwksUnknownKidRefreshMin = 5 * time.Minute

	jwksFetchTimeout = 15 * time.Second
	maxJWKSBody      = 1 << 20 // 1 MiB
)

// botClaims are the claims the adapter reads from a verified token.
type botClaims struct {
	Issuer     string `json:"iss"`
	Audience   string `json:"aud"`
	ServiceURL string `json:"serviceurl"`
	NotBefore  int64  `json:"nbf"`
	Expiry     int64  `json:"exp"`
}

type jwtHeader struct {
	Alg string `json:"alg"`
	Kid string `json:"kid"`
	Typ string `json:"typ"`
}

type openIDConfig struct {
	JWKSURI string `json:"jwks_uri"`
}

type jwk struct {
	Kty string `json:"kty"`
	Kid string `json:"kid"`
	Use string `json:"use"`
	N   string `json:"n"`
	E   string `json:"e"`
}

type jwks struct {
	Keys []jwk `json:"keys"`
}

// tokenVerifier verifies Bot Framework bearer tokens for one app id.
type tokenVerifier struct {
	openIDConfigURL string
	audience        string
	client          *http.Client
	now             func() time.Time

	mu          sync.Mutex
	keys        map[string]*rsa.PublicKey
	fetchedAt   time.Time
	lastUnknown time.Time
	// lastFetchFail is when a fetch last failed; the stale and cold paths
	// back off from it so an unreachable Microsoft is not re-dialled on
	// every request.
	lastFetchFail time.Time
	// fetching serialises fetches without holding mu across the network;
	// fetchGen counts completed fetches so a waiter can tell whether the
	// fetch it queued behind already did its work.
	fetching sync.Mutex
	fetchGen uint64
}

func newTokenVerifier(openIDConfigURL, audience string) *tokenVerifier {
	return &tokenVerifier{
		openIDConfigURL: openIDConfigURL,
		audience:        audience,
		client:          http.DefaultClient,
		now:             time.Now,
	}
}

// verify checks an Authorization header value and returns the token's
// claims. Every failure is an error; the caller treats them all as 401.
func (v *tokenVerifier) verify(ctx context.Context, authorization string) (*botClaims, error) {
	const prefix = "Bearer "
	if len(authorization) <= len(prefix) || !strings.EqualFold(authorization[:len(prefix)], prefix) {
		return nil, errors.New("missing bearer token")
	}
	raw := strings.TrimSpace(authorization[len(prefix):])
	parts := strings.Split(raw, ".")
	if len(parts) != 3 {
		return nil, errors.New("malformed token")
	}
	headerJSON, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return nil, fmt.Errorf("decode header: %w", err)
	}
	var hdr jwtHeader
	if err := json.Unmarshal(headerJSON, &hdr); err != nil {
		return nil, fmt.Errorf("parse header: %w", err)
	}
	// RS256 is the only algorithm the Bot Framework signs with. Refusing
	// anything else closes the classic alg-confusion hole where a token
	// declares "none" or an HMAC algorithm keyed by the public key.
	if hdr.Alg != "RS256" {
		return nil, fmt.Errorf("unsupported alg %q", hdr.Alg)
	}
	if hdr.Kid == "" {
		return nil, errors.New("token names no kid")
	}
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return nil, fmt.Errorf("decode signature: %w", err)
	}

	key, err := v.keyFor(ctx, hdr.Kid)
	if err != nil {
		return nil, err
	}
	digest := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	if err := rsa.VerifyPKCS1v15(key, crypto.SHA256, digest[:], sig); err != nil {
		return nil, errors.New("bad signature")
	}

	claimsJSON, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil, fmt.Errorf("decode claims: %w", err)
	}
	var claims botClaims
	if err := json.Unmarshal(claimsJSON, &claims); err != nil {
		return nil, fmt.Errorf("parse claims: %w", err)
	}
	if claims.Issuer != botFrameworkIssuer {
		return nil, fmt.Errorf("unexpected issuer %q", claims.Issuer)
	}
	if !strings.EqualFold(claims.Audience, v.audience) {
		return nil, errors.New("token audience is not this app")
	}
	now := v.now()
	if claims.Expiry == 0 || now.After(time.Unix(claims.Expiry, 0).Add(jwtClockSkew)) {
		return nil, errors.New("token expired")
	}
	if claims.NotBefore != 0 && now.Before(time.Unix(claims.NotBefore, 0).Add(-jwtClockSkew)) {
		return nil, errors.New("token not yet valid")
	}
	return &claims, nil
}

// prefetch warms the key cache so the first inbound request does not pay
// for the JWKS round-trip. Failure is logged, not fatal: the first request
// will try again, and the adapter must come up even when Microsoft's
// metadata endpoint is briefly unreachable.
func (v *tokenVerifier) prefetch(ctx context.Context) error {
	_, err := v.keyFor(ctx, "")
	if err != nil && strings.HasPrefix(err.Error(), "unknown signing key") {
		return nil // fetched fine; the empty kid is just not in it
	}
	return err
}

// keyFor returns the public key for a kid, fetching or refreshing the JWKS
// as needed. The decision to fetch is made under mu; the fetch itself runs
// under a separate mutex so concurrent requests on a cold or stale cache
// wait for one fetch rather than each starting their own, and so requests
// that only need a cached key are never blocked behind the network.
func (v *tokenVerifier) keyFor(ctx context.Context, kid string) (*rsa.PublicKey, error) {
	v.mu.Lock()
	now := v.now()
	gen := v.fetchGen
	if v.keys != nil && now.Sub(v.fetchedAt) <= jwksTTL {
		if k, ok := v.keys[kid]; ok {
			v.mu.Unlock()
			return k, nil
		}
		// Unknown kid on a fresh cache: Microsoft may have rolled keys.
		// Refresh early, but not more than once per window, so a stream of
		// forged tokens with random kids cannot drive fetches.
		if now.Sub(v.lastUnknown) < jwksUnknownKidRefreshMin {
			v.mu.Unlock()
			return nil, fmt.Errorf("unknown signing key %q", kid)
		}
		v.lastUnknown = now
	} else if now.Sub(v.lastFetchFail) < jwksUnknownKidRefreshMin {
		// Cold or stale cache and a fetch failed recently: do not hammer
		// Microsoft on every request. Serve the stale set if it has the key.
		if k, ok := v.keys[kid]; ok {
			v.mu.Unlock()
			return k, nil
		}
		v.mu.Unlock()
		return nil, errors.New("signing keys unavailable (recent fetch failed; retrying shortly)")
	}
	v.mu.Unlock()

	v.fetching.Lock()
	defer v.fetching.Unlock()
	// Another request may have completed a fetch while this one waited.
	v.mu.Lock()
	if v.fetchGen != gen {
		k, ok := v.keys[kid]
		v.mu.Unlock()
		if ok {
			return k, nil
		}
		return nil, fmt.Errorf("unknown signing key %q", kid)
	}
	v.mu.Unlock()

	keys, err := v.fetchKeys(ctx)

	v.mu.Lock()
	defer v.mu.Unlock()
	if err != nil {
		v.lastFetchFail = v.now()
		// Keep serving the old set rather than failing closed on a
		// transient fetch error, but the requested kid still has to be
		// in it.
		if k, ok := v.keys[kid]; ok {
			return k, nil
		}
		return nil, fmt.Errorf("fetch signing keys: %w", err)
	}
	v.keys = keys
	v.fetchedAt = v.now()
	v.fetchGen++
	if k, ok := keys[kid]; ok {
		return k, nil
	}
	return nil, fmt.Errorf("unknown signing key %q", kid)
}

// fetchKeys follows the OpenID configuration document to its JWKS and
// parses every usable RSA key.
func (v *tokenVerifier) fetchKeys(ctx context.Context) (map[string]*rsa.PublicKey, error) {
	ctx, cancel := context.WithTimeout(ctx, jwksFetchTimeout)
	defer cancel()
	var cfg openIDConfig
	if err := v.getJSON(ctx, v.openIDConfigURL, &cfg); err != nil {
		return nil, fmt.Errorf("openid configuration: %w", err)
	}
	if !strings.HasPrefix(cfg.JWKSURI, "https://") {
		return nil, fmt.Errorf("openid configuration names a non-https jwks_uri %q", cfg.JWKSURI)
	}
	var set jwks
	if err := v.getJSON(ctx, cfg.JWKSURI, &set); err != nil {
		return nil, fmt.Errorf("jwks: %w", err)
	}
	keys := map[string]*rsa.PublicKey{}
	for _, k := range set.Keys {
		if k.Kty != "RSA" || k.Kid == "" || (k.Use != "" && k.Use != "sig") {
			continue
		}
		pub, err := rsaKeyFromJWK(k)
		if err != nil {
			continue // one malformed key must not poison the set
		}
		keys[k.Kid] = pub
	}
	if len(keys) == 0 {
		return nil, errors.New("jwks contained no usable RSA signing keys")
	}
	return keys, nil
}

func (v *tokenVerifier) getJSON(ctx context.Context, target string, out any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		return err
	}
	resp, err := v.client.Do(req)
	if err != nil {
		return err
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("http %d from %s", resp.StatusCode, target)
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxJWKSBody))
	if err != nil {
		return err
	}
	return json.Unmarshal(body, out)
}

// rsaKeyFromJWK builds an RSA public key from the base64url modulus and
// exponent a JWK carries.
func rsaKeyFromJWK(k jwk) (*rsa.PublicKey, error) {
	nBytes, err := base64.RawURLEncoding.DecodeString(k.N)
	if err != nil {
		return nil, fmt.Errorf("modulus: %w", err)
	}
	eBytes, err := base64.RawURLEncoding.DecodeString(k.E)
	if err != nil {
		return nil, fmt.Errorf("exponent: %w", err)
	}
	if len(nBytes) == 0 || len(eBytes) == 0 || len(eBytes) > 8 {
		return nil, errors.New("malformed modulus or exponent")
	}
	e := 0
	for _, b := range eBytes {
		e = e<<8 | int(b)
	}
	if e < 3 {
		return nil, errors.New("exponent too small")
	}
	n := new(big.Int).SetBytes(nBytes)
	if n.BitLen() < 2048 {
		return nil, fmt.Errorf("modulus too short (%d bits)", n.BitLen())
	}
	return &rsa.PublicKey{N: n, E: e}, nil
}
