# Duplicate investigation order

No duplicate verdict is supplied. Investigate candidates before applying the existing triage policy.

## Source issue
429 responses retry without delay
The HTTP client ignores Retry-After on 429 and immediately retries.

## Candidate 1: C2
Honor Retry-After on rate limits
For 429, the HTTP client ignores the Retry-After header and retries at once.

## Candidate 2: C1
Retries ignore 503 backoff
503 responses retry immediately; the client has a different 503 retry implementation.
