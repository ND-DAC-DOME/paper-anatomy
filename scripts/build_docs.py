#!/usr/bin/env python3
"""Build the published documentation site under docs/ (GitHub Pages source).

Deterministic by construction: Widoco 1.4.25 with these flags emits no
wall-clock timestamps (verified — all dates come from the ontology's own
dcterms metadata), so CI can regenerate and `git diff --exit-code docs/`.

Layout produced (reviewer-approved, 2026-07-15):
  docs/
  ├── index.html          ← hand-authored landing (NOT touched by this script)
  ├── vocab/              ← Widoco-generated spec + serializations
  ├── shapes/             ← index.html (hand-authored, NOT touched) + copied *.ttl
  ├── releases/           ← copied from the repo-root releases/ (source of truth)
  └── resources/quality/  ← per-release validation evidence (captured at release
                            time via --quality; not regenerated on every build)

Usage:
    python3 scripts/build_docs.py            # regenerate vocab/, sync shapes/releases
    python3 scripts/build_docs.py --quality  # also capture validation evidence
                                             # (runs validate.py + formal_checks.py; slow, needs Java)
"""

import hashlib
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"

# Pinned Widoco artifact (reviewer requirement: exact artifact, not a moving branch)
WIDOCO_VERSION = "1.4.25"
WIDOCO_URL = ("https://github.com/dgarijo/Widoco/releases/download/"
              f"v{WIDOCO_VERSION}/widoco-{WIDOCO_VERSION}-jar-with-dependencies_JDK-17.jar")
WIDOCO_SHA256 = "be57a270fffb91e55810fa308717e704a44e2e7c027a3d68125a49da6c8b4e2b"
WIDOCO_JAR = Path.home() / ".cache" / "widoco" / f"widoco-{WIDOCO_VERSION}-JDK-17.jar"


def ensure_widoco() -> Path:
    if not WIDOCO_JAR.exists():
        print(f"Downloading Widoco {WIDOCO_VERSION} …")
        WIDOCO_JAR.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(WIDOCO_URL, WIDOCO_JAR)
    digest = hashlib.sha256(WIDOCO_JAR.read_bytes()).hexdigest()
    if digest != WIDOCO_SHA256:
        sys.exit(f"Widoco jar sha256 mismatch: {digest} != {WIDOCO_SHA256} — refusing to run")
    return WIDOCO_JAR


def build_vocab():
    """Widoco spec + serializations into docs/vocab/."""
    jar = ensure_widoco()
    out = DOCS / "vocab"
    if out.exists():
        shutil.rmtree(out)
    res = subprocess.run(
        ["java", "-jar", str(jar),
         "-ontFile", str(REPO / "pax.ttl"),
         "-outFolder", str(out),
         "-getOntologyMetadata", "-rewriteAll", "-uniteSections", "-noPlaceHolderText"],
        capture_output=True, text=True)
    if "Documentation generated successfully" not in (res.stdout + res.stderr):
        sys.exit(f"Widoco failed:\n{res.stderr[-2000:]}")
    # GitHub Pages needs index.html; Widoco names it index-en.html
    shutil.copy(out / "index-en.html", out / "index.html")
    print(f"  vocab/ generated (Widoco {WIDOCO_VERSION})")


def sync_shapes():
    """Copy the SHACL profiles next to their hand-authored index page."""
    out = DOCS / "shapes"
    out.mkdir(parents=True, exist_ok=True)
    for f in sorted((REPO / "shapes").glob("*.ttl")):
        shutil.copy(f, out / f.name)
    print("  shapes/*.ttl synced")


def sync_releases():
    """Repo-root releases/ is the source of truth; docs/releases/ is the served copy."""
    src, out = REPO / "releases", DOCS / "releases"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    print("  releases/ synced")


def capture_quality():
    """Run both validation layers and archive their evidence for the current release."""
    qdir = DOCS / "resources" / "quality" / "0.2.0"
    qdir.mkdir(parents=True, exist_ok=True)
    for script, deps, log in (
            ("validate.py", ["rdflib", "pyshacl"], "validate.log"),
            ("formal_checks.py", ["rdflib", "pyld"], "formal_checks.log")):
        cmd = ["uv", "run"] + [x for d in deps for x in ("--with", d)] + ["python", script]
        res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        (qdir / log).write_text(res.stdout + res.stderr)
        status = "OK" if res.returncode == 0 else "FAILED"
        print(f"  {script}: {status} → resources/quality/0.2.0/{log}")
        if res.returncode != 0:
            sys.exit(1)
    # machine-readable artifacts from the formal layer
    fc_out = REPO / "output" / "formal_checks"
    for name in ("lint-report.tsv", "profile-pax.txt"):
        if (fc_out / name).exists():
            shutil.copy(fc_out / name, qdir / name)
    print("  quality evidence captured")


def main():
    DOCS.mkdir(exist_ok=True)
    build_vocab()
    sync_shapes()
    sync_releases()
    if "--quality" in sys.argv:
        capture_quality()
    print("docs/ build complete")


if __name__ == "__main__":
    main()
