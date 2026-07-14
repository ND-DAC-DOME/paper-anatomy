#!/usr/bin/env python3
"""Fetch pinned local copies of the vocabularies pax.ttl builds on.

The formal checks (HermiT reasoning, OWL profile) must run against a PINNED
dependency closure, not whatever the web serves today. This script downloads
each dependency into kg/imports/ (committed to git); re-run deliberately when
you want to bump the pins.

    uv run python kg/fetch_imports.py
"""

import sys
import urllib.request
from pathlib import Path

IMPORTS_DIR = Path(__file__).parent / "imports"

# (filename, url, Accept header)
SOURCES = [
    ("doco.ttl",  "http://purl.org/spar/doco.ttl", None),
    ("deo.ttl",   "http://purl.org/spar/deo.ttl", None),
    ("fabio.ttl", "http://purl.org/spar/fabio.ttl", None),
    ("pattern.ttl", "https://w3id.org/spar/po", "text/turtle"),  # PO moved into the SPAR family
    ("oa.ttl",    "https://www.w3.org/ns/oa.ttl", None),
    ("prov.ttl",  "https://www.w3.org/ns/prov.ttl", None),
    ("skos.rdf",  "https://www.w3.org/2009/08/skos-reference/skos.rdf", None),
    ("frbr-core.rdf", "http://purl.org/vocab/frbr/core.rdf", "application/rdf+xml"),
    ("dcterms.ttl", "https://www.dublincore.org/specifications/dublin-core/dcmi-terms/dublin_core_terms.ttl", None),
    ("foaf.rdf",  "http://xmlns.com/foaf/spec/index.rdf", "application/rdf+xml"),
]


def main():
    IMPORTS_DIR.mkdir(exist_ok=True)
    failed = []
    for fname, url, accept in SOURCES:
        dest = IMPORTS_DIR / fname
        req = urllib.request.Request(url, headers={
            "User-Agent": "paper-atomizer-kg/0.2 (vocabulary dependency pinning)",
            **({"Accept": accept} if accept else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            dest.write_bytes(data)
            print(f"  ✓ {fname:16s} {len(data)//1024:5d} KB  {url}")
        except Exception as e:
            print(f"  ✗ {fname:16s} FAILED: {e}")
            failed.append(fname)
    if failed:
        print(f"\n{len(failed)} download(s) failed: {failed}")
        sys.exit(1)
    print("\nAll imports pinned.")


if __name__ == "__main__":
    main()
