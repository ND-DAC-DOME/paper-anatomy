#!/usr/bin/env python3
"""Formal checks for the Paper Anatomy Vocabulary — slow CI layer.

Complements kg/validate.py (fast checks) with:
  [M] merge pax.ttl + the pinned dependency closure (kg/imports/) into one
      self-contained graph (owl:imports stripped so nothing is fetched live)
  [P] OWL 2 DL profile validation (ROBOT/OWLAPI) — pax-related violations fail;
      violations inherited from imported vocabularies are reported, not fatal
  [H] HermiT consistency + unsatisfiable-class check over the merged closure
  [L] ROBOT report (vocabulary lint) on pax.ttl alone
  [J] pyld expansion round-trip of the example JSON-LD

Requirements: Java (for ROBOT; jar auto-downloaded to ~/.cache/robot/) and
    uv run --with rdflib --with pyld python kg/formal_checks.py

Outputs land in output/kg_formal_checks/ (not tracked).
"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from rdflib import Graph, OWL, RDF

KG_DIR = Path(__file__).parent
OUT = KG_DIR / "output" / "formal_checks"
ROBOT_JAR = Path.home() / ".cache" / "robot" / "robot.jar"
ROBOT_URL = "https://github.com/ontodev/robot/releases/latest/download/robot.jar"

failures: list[str] = []


def check(ok: bool, msg: str):
    print(("  ✓ " if ok else "  ✗ ") + msg)
    if not ok:
        failures.append(msg)


def robot(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["java", "-jar", str(ROBOT_JAR), *args],
        capture_output=True, text=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    if not ROBOT_JAR.exists():
        print(f"Downloading ROBOT to {ROBOT_JAR} …")
        ROBOT_JAR.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(ROBOT_URL, ROBOT_JAR)

    # ---- [M] merged, self-contained closure ----
    print("[M] merge pinned closure")
    merged = Graph()
    merged.parse(KG_DIR / "pax.ttl", format="turtle")
    n_pax = len(merged)
    for f in sorted((KG_DIR / "imports").iterdir()):
        fmt = "turtle" if f.suffix == ".ttl" else "xml"
        merged.parse(f, format=fmt)
    removed = 0
    for s, pr, o in list(merged.triples((None, OWL.imports, None))):
        merged.remove((s, pr, o))
        removed += 1
    # The Pattern Ontology ships SWRL rules with built-in atoms, which
    # HermiT-in-ROBOT does not support; they are PO's, not ours — strip them
    # from the reasoning closure.
    from rdflib import URIRef
    SWRL = "http://www.w3.org/2003/11/swrl"
    def is_swrl(t):
        return any(isinstance(x, URIRef) and str(x).startswith(SWRL) for x in t)
    swrl_nodes = {s for s, pr, o in merged if is_swrl((s, pr, o))}
    n_swrl = 0
    changed = True
    while changed:  # follow bnode list structure reachable from SWRL triples
        changed = False
        for t in list(merged):
            if is_swrl(t) or t[0] in swrl_nodes:
                if t[2] not in swrl_nodes:
                    swrl_nodes.add(t[2])
                    changed = True
                merged.remove(t)
                n_swrl += 1
    merged_path = OUT / "merged.ttl"
    merged.serialize(merged_path, format="turtle")
    check(True, f"{len(merged)} triples ({n_pax} pax + closure; "
                f"{removed} owl:imports and {n_swrl} SWRL triples stripped)")

    # ---- [P] OWL 2 DL profile ----
    # Gate: pax.ttl STANDALONE must be in OWL 2 DL. The full merged closure is
    # checked informationally only — mixed legacy vocabularies (foaf, dcterms
    # as plain rdf:Property) make closure-wide DL conformance unattainable,
    # which is a documented finding, not a pax defect.
    print("[P] OWL 2 DL profile (ROBOT/OWLAPI)")
    res = robot("validate-profile", "--profile", "DL",
                "--input", str(KG_DIR / "pax.ttl"),
                "--output", str(OUT / "profile-pax.txt"))
    report = (OUT / "profile-pax.txt").read_text() if (OUT / "profile-pax.txt").exists() else res.stderr
    ok = "Ontology and imports closure in profile" in report
    viol = [l for l in report.splitlines() if l.strip() and "Violation" not in l and "in profile" not in l]
    check(ok, "pax.ttl standalone is in OWL 2 DL"
              if ok else f"pax.ttl NOT in DL — {len(viol)} violation(s), see profile-pax.txt")
    if not ok:
        for l in viol[:5]:
            print(f"      {l.strip()[:110]}")
    robot("validate-profile", "--profile", "DL",
          "--input", str(merged_path),
          "--output", str(OUT / "profile-closure.txt"))
    closure_report = (OUT / "profile-closure.txt").read_text() if (OUT / "profile-closure.txt").exists() else ""
    n_closure = sum(1 for l in closure_report.splitlines() if l.strip()) - 1
    print(f"  · informational: merged closure has ~{max(n_closure,0)} DL violations "
          f"(inherited from legacy imports; see profile-closure.txt)")

    # ---- [H] HermiT consistency ----
    print("[H] HermiT reasoning over the TRANSFORMED closure (SWRL stripped)")
    res = robot("reason", "--reasoner", "hermit",
                "--input", str(merged_path),
                "--output", str(OUT / "reasoned.ttl"))
    if res.returncode == 0:
        check(True, "consistent; no unsatisfiable classes")
    else:
        err = (res.stderr or res.stdout).strip().splitlines()
        summary = next((l for l in err if "unsatisfiable" in l.lower() or "inconsistent" in l.lower()),
                       err[-1] if err else "unknown error")
        check(False, f"reasoning failed: {summary[:140]}")

    # ---- [L] vocabulary lint on pax.ttl alone ----
    print("[L] ROBOT report (lint) on pax.ttl")
    res = robot("report", "--input", str(KG_DIR / "pax.ttl"),
                "--output", str(OUT / "lint-report.tsv"),
                "--print", "10")
    tsv = OUT / "lint-report.tsv"
    if tsv.exists():
        rows = [r.split("\t") for r in tsv.read_text().splitlines()[1:] if r.strip()]
        by_level = {}
        for r in rows:
            by_level.setdefault(r[0], []).append(r)
        errors = by_level.get("ERROR", [])
        summary = ", ".join(f"{len(v)} {k.lower()}" for k, v in sorted(by_level.items())) or "clean"
        check(len(errors) == 0, f"lint: {summary} (full report: lint-report.tsv)")
        for r in errors[:5]:
            print(f"      ERROR {r[1].split('#')[-1] if len(r) > 1 else ''}: {r[2].split('#')[-1] if len(r) > 2 else ''}")
    else:
        check(False, f"robot report failed: {(res.stderr or '')[:140]}")

    # ---- [J] pyld round-trip of the example ----
    print("[J] pyld JSON-LD expansion round-trip")
    try:
        from pyld import jsonld
        doc = json.loads((KG_DIR / "examples" / "Mercadier2011.jsonld").read_text())
        expanded = jsonld.expand(doc)
        compacted = jsonld.compact(expanded, doc["@context"])
        n_in = len(doc["@graph"])
        n_out = len(compacted.get("@graph", []))
        check(n_in == n_out, f"expand/compact preserves node count ({n_in} → {n_out})")
    except ImportError:
        check(False, "pyld not available — run with: uv run --with rdflib --with pyld")
    except Exception as e:
        check(False, f"pyld round-trip failed: {type(e).__name__}: {str(e)[:120]}")

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        sys.exit(1)
    print("ALL FORMAL CHECKS PASSED")


if __name__ == "__main__":
    main()
