This is the `build-base` shared implementation drain stage. Treat it as a
virtual contract that concrete formulas may override.

Drain the decomposed implementation convoy in one shared session using the
selected implementation target {{implementation_target}}. Preserve item
order, stop on item failure, and record the implementation drain manifest on
the workflow root.

Close this step only after all assigned implementation work has either passed
or has an explicit failure artifact.
