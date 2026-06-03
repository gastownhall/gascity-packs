"""ast-lens write-side spine.

A clean-room implementation of the compile-gate + plan/execute pair contract
from "The AST as LLM Lens" (sec 5.5 plan/execute, sec 5.6 compile gate,
sec 3 false-negative-only contract).

The read-side (``bin/outline.py``) emits AST outlines that auto-prepend to a
``Read``. The write-side mirrors that lens for *symbolic surgery*: an agent
issues a transform *intent* on a file, the framework emits a content-addressed
*plan* (read-only), and a later *execute* commits the plan through a compile
*gate* that is false-negative-only by construction — it may reject a safe diff,
but never accepts one that breaks the program.

Public surface:
  - :mod:`astlens.ops`        registered ops; each exposes ``compute_change``.
  - :func:`astlens.gate.gate` the compile gate (accept iff all touched files
                              pass their native syntax check).
  - :mod:`astlens.plan`       ``make_plan`` / ``render_plan`` / ``execute``.
  - :func:`astlens.registry.resolve`  op name -> ``compute_change`` (guarded).
"""

__all__ = ["gate", "plan", "registry", "ops"]
