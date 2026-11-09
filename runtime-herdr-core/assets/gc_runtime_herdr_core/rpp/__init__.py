"""The provider-neutral RPP v0 kit.

Wire shapes (:mod:`.wire`), exit codes (:mod:`.exitcodes`), ops and their
table (:mod:`.ops`), the per-op runner (:mod:`.perop`), cancellation and
deadlines (:mod:`.cancel`), stderr redaction (:mod:`.redact`), file locks
(:mod:`.flock`), the private state root and city key (:mod:`.statedir`) and
typed JSON access (:mod:`.jsonval`). Nothing here names a backend.
"""

from __future__ import annotations
