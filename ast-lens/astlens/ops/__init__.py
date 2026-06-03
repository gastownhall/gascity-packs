"""ast-lens ops package.

Each op is ``astlens/ops/<name>.py`` exposing EXACTLY::

    def compute_change(file_path: str, args: dict) -> dict | None

returning ``{relpath: new_full_content}`` for EVERY file it changes (relpath
relative to the repo root = git root above ``file_path``, else its dir), or
``None`` if there is nothing to change / it cannot do so safely.

Ops are pure: they NEVER write files. Writing is the exclusive job of
:func:`astlens.plan.execute`, and only after the compile :func:`astlens.gate.gate`
returns ``accept``.

The only op owned by the spine is :mod:`astlens.ops.strip_trailing_ws`, the
language-agnostic demo op used to prove the framework end-to-end. The other
ops (``fix-imports``, ``rename-symbol``, ``extract-to-package``) are supplied
by sibling modules and registered defensively in :mod:`astlens.registry` —
an absent op module is skipped, never fatal.
"""
