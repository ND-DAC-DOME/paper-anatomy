#!/usr/bin/env python3
"""Spike fidelity tests: can the LinkML-generated artifacts handle real PAX data?

[A] Pydantic: parse ALL 78 nodes of the real Mercadier graph through the
    generated models (with the JSON-LD shim documented in FINDINGS.md).
[B] Context: compare the generated JSON-LD context against the hand-authored
    context.jsonld — every shared term must expand to the SAME IRI.

Run:  uv run --with pydantic python linkml/test_roundtrip.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "generated"))
import pax_instance as m  # noqa: E402

failures = []


def check(ok, msg):
    print(("  ✓ " if ok else "  ✗ ") + msg)
    if not ok:
        failures.append(msg)


# ------------------------------------------------------------------ [A] shim

_blank = 0


def normalize(obj):
    """JSON-LD compacted node -> Pydantic kwargs.
    The shim IS a finding: '@id'/'@type' are not valid Python field names, and
    blank nodes (regions, selectors) have no '@id' while LinkML identifiers
    are required — synthesized here."""
    global _blank
    if isinstance(obj, list):
        return [normalize(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if k == "@id":
            out["id"] = v
        elif k == "@type":
            out["category"] = v if isinstance(v, list) else [v]
        elif k.startswith("pax:"):
            # exporters emit prefixed CURIE keys for terms the context defines
            # no shortcut for (level, matter, pageStart, pageEnd, parsedContent)
            out[k[4:]] = normalize(v)
        else:
            out[k] = normalize(v)
    if "id" not in out and "category" in out:  # blank node
        _blank += 1
        out["id"] = f"_:b{_blank}"
    return out


DISPATCH = [
    ("fabio:JournalArticle", m.PaperExpression),
    ("fabio:DigitalManifestation", m.Manifestation),
    ("fabio:Page", m.Page),
    ("doco:FrontMatter", m.Matter), ("doco:BodyMatter", m.Matter), ("doco:BackMatter", m.Matter),
    ("doco:Section", m.Section),
    ("doco:FigureBox", m.Box), ("doco:TableBox", m.Box),
    ("sdo:Dataset", m.Dataset), ("schema:Dataset", m.Dataset),
    ("prov:Activity", m.Activity),
    ("prov:SoftwareAgent", m.SoftwareAgent),
    ("fabio:SupplementaryInformationFile", m.Supplement),
]


def model_for(types):
    for t, cls in DISPATCH:
        if t in types:
            return cls
    return m.DocumentElement


def test_pydantic_parse():
    print("[A] Pydantic models parse the real graph")
    kg = json.loads((HERE.parent / "examples" / "Mercadier2011.jsonld").read_text())
    ok, errors = 0, []
    for node in kg["@graph"]:
        cls = model_for(node.get("@type", []) if isinstance(node.get("@type"), list)
                        else [node.get("@type")])
        try:
            cls(**normalize(node))
            ok += 1
        except Exception as e:
            errors.append(f"{node['@id'].split('/mercadier2011/')[-1]} ({cls.__name__}): "
                          f"{str(e).splitlines()[0][:90]}")
    check(ok == len(kg["@graph"]),
          f"{ok}/{len(kg['@graph'])} nodes parse ({len(errors)} failures)")
    for e in errors[:8]:
        print("      ✗", e)

    # negative test: the models must actually REJECT bad data
    bad = dict(id="x", category=["fabio:Page"], position="not-an-int")
    try:
        m.Page(**bad)
        check(False, "Page accepted a non-integer position — validation is vacuous")
    except Exception:
        check(True, "Page rejects a non-integer position (validation is real)")
    try:
        m.Page(id="x", category=["fabio:Page"], bogusField=1)
        check(False, "Page accepted an unknown field — extra=forbid not effective")
    except Exception:
        check(True, "Page rejects unknown fields")


# ------------------------------------------------------------------ [B] context

def expand(term_def, prefixes):
    iri = term_def["@id"] if isinstance(term_def, dict) else term_def
    if ":" in iri:
        pfx, local = iri.split(":", 1)
        if pfx in prefixes and not local.startswith("//"):
            base = prefixes[pfx]
            base = base["@id"] if isinstance(base, dict) else base
            return base + local
    return iri


def test_context_fidelity():
    print("[B] generated context vs hand-authored context.jsonld")
    ours = json.loads((HERE.parent / "context.jsonld").read_text())["@context"]
    gen = json.loads((HERE / "generated" / "context.jsonld").read_text())["@context"]
    our_pfx = {k: v for k, v in ours.items() if isinstance(v, str) and v.startswith("http")}
    gen_pfx = {k: v for k, v in gen.items()
               if (isinstance(v, str) and v.startswith("http"))
               or (isinstance(v, dict) and str(v.get("@id", "")).startswith("http")
                   and v.get("@prefix"))}
    our_terms = {k: expand(v, our_pfx) for k, v in ours.items()
                 if k not in our_pfx and not k.startswith("@")}
    gen_terms = {k: expand(v, gen_pfx) for k, v in gen.items()
                 if k not in gen_pfx and not k.startswith("@") and isinstance(v, (dict, str))}

    shared = set(our_terms) & set(gen_terms)
    same = {t for t in shared if our_terms[t] == gen_terms[t]}
    diff = {t: (our_terms[t], gen_terms[t]) for t in shared - same}
    missing = set(our_terms) - set(gen_terms)
    check(len(same) > 0, f"{len(same)}/{len(shared)} shared terms expand to the same IRI")
    check(not diff, f"terms expanding differently: { {k: v for k, v in list(diff.items())[:4]} or 'none'}")
    print(f"  · hand-authored terms not in generated context: {len(missing)} "
          f"({sorted(missing)[:6]}{'…' if len(missing) > 6 else ''})")


def main():
    test_pydantic_parse()
    test_context_fidelity()
    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        sys.exit(1)
    print("ALL SPIKE CHECKS PASSED")


if __name__ == "__main__":
    main()
