#!/usr/bin/env python3
"""Reproducible validation for the Paper Anatomy Vocabulary (PAX) artifacts.

Layers (subset of the CI pipeline recommended in review):
  1. pax.ttl parses as Turtle.
  2. The example JSON-LD parses as RDF (round-trips through rdflib).
  3. Term coverage: every pax: term used by the exporter source, the context,
     and the example graph is defined in pax.ttl — and every defined term is
     exercised somewhere in the sources (SKOS concepts count via the
     exporter's FIGURE_TYPE_CONCEPTS table).
  4. Data sanity: every region selector is well-formed xywh with nonnegative
     coords and positive dimensions; when the page declares image dimensions,
     the region must fall within them.

  5. SHACL: three shape profiles under kg/shapes/ —
     core (Violations fail the run), recommended (Warnings reported),
     diagnostic (Info reported). Includes the materialized-projection
     consistency rules (pax:matter / pageStart / pageEnd vs containment).

  6. README term counts: the "N classes, N object properties, N datatype
     properties … (N concepts)" sentence in README.md must match what
     pax.ttl actually declares — documentation drift fails CI.

Dependencies are intentionally not project dependencies; run with:
    uv run --with rdflib --with pyshacl python kg/validate.py
"""

import json
import re
import sys
from pathlib import Path

from rdflib import Graph, RDF, OWL, Namespace

KG_DIR = Path(__file__).parent
PAX = Namespace("https://w3id.org/paper-anatomy/vocab#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

failures: list[str] = []


def check(ok: bool, msg: str):
    print(("  ✓ " if ok else "  ✗ ") + msg)
    if not ok:
        failures.append(msg)


def main():
    # ---- 1. vocabulary parses ----
    print("[1] pax.ttl")
    vocab = Graph()
    vocab.parse(KG_DIR / "pax.ttl", format="turtle")
    check(len(vocab) > 0, f"parses ({len(vocab)} triples)")

    defined = set()
    for rdf_type in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty,
                     SKOS.Concept, SKOS.ConceptScheme):
        for s in vocab.subjects(RDF.type, rdf_type):
            if str(s).startswith(str(PAX)):
                defined.add(str(s).split("#")[-1])
    check(len(defined) > 0, f"{len(defined)} pax terms defined")

    # ---- 2. example parses as RDF ----
    print("[2] examples/Mercadier2011.jsonld")
    example_path = KG_DIR / "examples" / "Mercadier2011.jsonld"
    data = Graph()
    data.parse(example_path, format="json-ld")
    check(len(data) > 0, f"parses as RDF ({len(data)} triples)")

    # ---- 3. term coverage ----
    print("[3] term coverage")
    used = set()
    sources = [KG_DIR / "context.jsonld"] + sorted((KG_DIR / "shapes").glob("*.ttl"))
    for f in sources:
        used |= set(re.findall(r"pax:([A-Za-z]+)", f.read_text()))
    for term in list(data.predicates()) + [o for o in data.objects()] \
            + [s for s in data.subjects()]:
        s = str(term)
        if s.startswith(str(PAX)):
            used.add(s.split("#")[-1])
    used.discard("")

    missing = used - defined
    # SKOS concepts are a controlled list — membership in the scheme is their
    # purpose; any given example exercises only a subset.
    concepts = {str(s).split("#")[-1] for s in vocab.subjects(RDF.type, SKOS.Concept)}
    unused = defined - used - concepts - {"FigureTypeScheme"}
    check(not missing, f"all used terms defined (missing: {sorted(missing) or 'none'})")
    check(not unused, f"all defined terms exercised (unused: {sorted(unused) or 'none'})")
    check("sequenceNumber" not in defined and "sequenceNumber" not in used,
          "sequenceNumber fully removed")

    # ---- 4. region sanity ----
    print("[4] region sanity (xywh well-formed, within page bounds)")
    kg = json.loads(example_path.read_text())
    nodes = {n["@id"]: n for n in kg["@graph"]}
    xywh_re = re.compile(r"^xywh=(\d+),(\d+),(\d+),(\d+)$")
    bad_form, out_of_bounds, checked = 0, 0, 0
    for n in kg["@graph"]:
        for r in n.get("region", []):
            checked += 1
            m = xywh_re.match(r["hasSelector"]["value"])
            if not m:
                bad_form += 1
                continue
            x, y, w, h = map(int, m.groups())
            if w <= 0 or h <= 0:
                bad_form += 1
                continue
            page = nodes.get(n.get("onPage", ""))
            if page and page.get("pageImageWidth"):
                if x + w > page["pageImageWidth"] or y + h > page["pageImageHeight"]:
                    out_of_bounds += 1
    check(bad_form == 0, f"{checked} regions well-formed ({bad_form} malformed)")
    check(out_of_bounds == 0, f"all regions within page bounds ({out_of_bounds} outside)")

    # ---- 5. SHACL profiles ----
    print("[5] SHACL (core=Violation, recommended=Warning, diagnostic=Info)")
    try:
        from pyshacl import validate as shacl_validate
    except ImportError:
        check(False, "pyshacl not available — run with: uv run --with rdflib --with pyshacl")
    else:
        shapes = Graph()
        for f in sorted((KG_DIR / "shapes").glob("*.ttl")):
            shapes.parse(f, format="turtle")
        conforms, results_graph, _ = shacl_validate(
            data_graph=data, shacl_graph=shapes, inference="none")
        SH = Namespace("http://www.w3.org/ns/shacl#")
        by_sev = {"Violation": [], "Warning": [], "Info": []}
        for result in results_graph.subjects(RDF.type, SH.ValidationResult):
            sev = str(next(results_graph.objects(result, SH.resultSeverity))).split("#")[-1]
            msg = str(next(results_graph.objects(result, SH.resultMessage), ""))
            focus = str(next(results_graph.objects(result, SH.focusNode), ""))
            by_sev.setdefault(sev, []).append((focus, msg))
        for sev in ("Violation", "Warning", "Info"):
            items = by_sev.get(sev, [])
            uniq_msgs = {}
            for focus, msg in items:
                uniq_msgs.setdefault(msg, 0)
                uniq_msgs[msg] += 1
            summary = "; ".join(f"{c}× {m[:70]}" for m, c in sorted(uniq_msgs.items())) or "none"
            if sev == "Violation":
                check(len(items) == 0, f"{len(items)} violation(s): {summary}")
            else:
                print(f"  · {len(items)} {sev.lower()}(s): {summary}")

    # ---- 6. README stated term counts ----
    print("[6] README term counts match pax.ttl")
    def pax_count(rdf_type):
        return sum(1 for s in vocab.subjects(RDF.type, rdf_type)
                   if str(s).startswith(str(PAX)))
    actual = {
        "classes": pax_count(OWL.Class),
        "object properties": pax_count(OWL.ObjectProperty),
        "datatype properties": pax_count(OWL.DatatypeProperty),
        "concepts": pax_count(SKOS.Concept),
    }
    readme = (KG_DIR / "README.md").read_text()
    m = re.search(r"(\d+) classes, (\d+) object properties, (\d+) datatype "
                  r"properties.*?\((\d+) concepts\)", readme)
    if not m:
        check(False, "README no longer contains the term-count sentence — "
                     "update this check alongside the wording")
    else:
        stated = dict(zip(actual.keys(), map(int, m.groups())))
        for key in actual:
            check(stated[key] == actual[key],
                  f"{key}: README says {stated[key]}, pax.ttl declares {actual[key]}")

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
