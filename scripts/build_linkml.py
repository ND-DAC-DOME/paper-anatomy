#!/usr/bin/env python3
"""Regenerate linkml/generated/ from linkml/pax-instance.yaml — pinned + deterministic.

Same contract as the docs build: a PINNED generator version (gen-pydantic output is
not stable across LinkML releases) and byte-deterministic output (the context's
`generation_date` stamp is stripped), so CI can regenerate and
`git diff --exit-code linkml/generated/`.

Usage:  python3 scripts/build_linkml.py
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "linkml" / "pax-instance.yaml"
OUT = REPO / "linkml" / "generated"

# Pinned generator (reviewer rule: exact artifact, not whatever pip serves today).
LINKML_VERSION = "1.11.1"

# gen-shacl is deliberately NOT here: its output is non-deterministic across
# runs (unordered sh:ignoredProperties) AND the spike verdict is that it cannot
# express our profiles anyway (FINDINGS.md) — generate ad hoc if curious.
GENERATORS = [
    ("gen-pydantic", "pax_instance.py"),
    ("gen-jsonld-context", "context.jsonld"),
    ("gen-json-schema", "schema.json"),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for tool, fname in GENERATORS:
        res = subprocess.run(
            ["uv", "run", "--with", f"linkml=={LINKML_VERSION}", tool, str(SCHEMA)],
            capture_output=True, text=True)
        if res.returncode != 0:
            sys.exit(f"{tool} failed:\n{res.stderr[-1500:]}")
        (OUT / fname).write_text(res.stdout)
        print(f"  {fname} generated ({tool}, linkml=={LINKML_VERSION})")

    # determinism: the context generator stamps a generation date — strip the
    # comments block (metadata about the run, not about the schema)
    ctx_path = OUT / "context.jsonld"
    ctx = json.loads(ctx_path.read_text())
    ctx.pop("comments", None)
    ctx_path.write_text(json.dumps(ctx, indent=2) + "\n")
    print("  context.jsonld normalized (generation stamp stripped)")

    # determinism ACROSS MACHINES: gen-pydantic embeds the schema's ABSOLUTE
    # path in linkml_meta.source_file (caught by the CI drift gate on its
    # first run — local /mnt/... vs runner /home/runner/...); rewrite it
    # repo-relative
    py_path = OUT / "pax_instance.py"
    src = py_path.read_text()
    src, n = re.subn(r"'source_file': '[^']*'",
                     "'source_file': 'linkml/pax-instance.yaml'", src)
    if n != 1:
        sys.exit(f"expected exactly one source_file entry in pax_instance.py, found {n}")
    py_path.write_text(src)
    print("  pax_instance.py normalized (source_file made repo-relative)")
    print("linkml/generated/ build complete")


if __name__ == "__main__":
    main()
