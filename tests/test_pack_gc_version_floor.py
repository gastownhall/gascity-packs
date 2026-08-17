"""A pack whose formulas need gc v1.3.0 must say so in `pack.toml`.

`[requires] formula_compiler` is the supported way for a formula to declare
the graph (v2) compiler, and gc only learned to read that table in v1.3.0
(`Requires *Requirements` first appears in `internal/formula/types.go` at that
tag). Older gc parses formula TOML leniently, so the table is not an error
there: it is dropped. A formula using graph-only constructs then fails to
compile, and a formula that does not use them silently takes the v1 path.

`requires_gc` in `[pack]` is where that floor is declared. Be precise about
what it buys: gc parses the key into `config.Pack.RequiresGC` and copies it
through `gc init`, and **nothing compares it against the running version**.
Refute with:

    grep -rn 'RequiresGC' --include=*.go <gascity checkout>/internal <gascity checkout>/cmd

So this test enforces a coupling inside the packs repo rather than claiming a
guarantee gc provides. The declaration is honest, greppable, and already in
the schema; it starts working the day a consumer lands, and until then it is
documentation in the place designed to hold it.

The pairing is what matters: a pack that adds a `formula_compiler` constraint
and forgets the floor ships formulas that quietly degrade on older gc, which
is exactly the regression the migration to `[requires]` introduced.
"""

from __future__ import annotations

import pathlib
import sys
import tomllib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from formula_compiler_requirement import declares_graph_compiler  # noqa: E402

# The gc release that first reads `[requires]` in a formula. Refute with:
#   git -C <gascity checkout> show v1.3.0:internal/formula/types.go \
#     | grep -n 'Requires \*Requirements'
REQUIRED_FLOOR = ">=1.3.0"

# Below this, the pack enumeration has broken rather than the repo having
# shrunk, and every assertion below would pass over an empty set.
MINIMUM_PACKS = 10


def packs() -> list[pathlib.Path]:
    """Every pack in the repo, from the tree rather than a hand-list."""
    return sorted(
        path.parent
        for path in REPO_ROOT.glob("*/pack.toml")
        if "__pycache__" not in path.parts
    )


def formulas_of(pack: pathlib.Path) -> list[pathlib.Path]:
    return sorted((pack / "formulas").glob("**/*.toml"))


class PackGCVersionFloorTest(unittest.TestCase):
    def test_the_guard_has_packs_to_check(self) -> None:
        found = packs()
        self.assertGreaterEqual(
            len(found),
            MINIMUM_PACKS,
            f"only {len(found)} packs found under {REPO_ROOT}; the enumeration "
            "is broken, so the assertions below would pass vacuously",
        )

    def test_every_pack_needing_the_v2_compiler_declares_the_floor(self) -> None:
        missing = []
        declaring = []
        for pack in packs():
            needs_v2 = False
            for formula in formulas_of(pack):
                try:
                    data = tomllib.loads(formula.read_text(encoding="utf-8"))
                except tomllib.TOMLDecodeError:
                    continue
                if declares_graph_compiler(data):
                    needs_v2 = True
                    break
            if not needs_v2:
                continue
            declaring.append(pack.name)
            manifest = tomllib.loads((pack / "pack.toml").read_text(encoding="utf-8"))
            floor = str(manifest.get("pack", {}).get("requires_gc", "")).strip()
            if floor != REQUIRED_FLOOR:
                missing.append(f"{pack.name}: requires_gc = {floor!r}")

        self.assertTrue(
            declaring,
            "no pack was found to need the v2 compiler; the formula scan is "
            "broken, since the repo ships dozens that declare it",
        )
        self.assertEqual(
            missing,
            [],
            "these packs ship formulas requiring the v2 graph compiler but do "
            f"not declare requires_gc = {REQUIRED_FLOOR!r} in [pack], so they "
            "install cleanly onto a gc that drops the declaration:\n  "
            + "\n  ".join(missing),
        )
