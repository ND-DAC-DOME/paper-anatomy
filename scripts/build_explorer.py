#!/usr/bin/env python3
"""Refresh the embedded graph data inside the interactive explorer page.

The explorer (docs/explorer/index.html — hand-authored UI, published on GitHub
Pages) is a self-contained page with the example JSON-LD compacted and inlined
as `const KG = {...};`. Whenever examples/Mercadier2011.jsonld is regenerated,
run this to re-inject (scripts/build_docs.py does it as part of the site build):

    python3 scripts/build_explorer.py \
        [--jsonld examples/Mercadier2011.jsonld] \
        [--html docs/explorer/index.html] [--page-w 1241 --page-h 1648]
"""

import argparse
import json
import re
from pathlib import Path


def compact(jsonld_path: Path, page_w: int, page_h: int) -> dict:
    kg = json.loads(jsonld_path.read_text())
    graph = {n["@id"]: n for n in kg["@graph"]}
    # base = the fabio:ResearchPaper IRI; keys are IRIs shortened against it
    def types_of(n):
        return n["@type"] if isinstance(n["@type"], list) else [n["@type"]]
    paper_iri = next(i for i, n in graph.items()
                     if "fabio:JournalArticle" in types_of(n)
                     or "fabio:ResearchPaper" in types_of(n))
    prefix = paper_iri + "/"
    short = lambda iri: iri[len(prefix):] if iri.startswith(prefix) else iri

    out = {}
    for iri, n in graph.items():
        types = n["@type"] if isinstance(n["@type"], list) else [n["@type"]]
        node = {"t": types}
        if n.get("title"):
            node["label"] = n["title"]
        if n.get("text"):
            node["text"] = n["text"][:400]
        if n.get("figureType"):
            node["fig"] = str(n["figureType"]).split(":")[-1]  # pax:lineGraph -> lineGraph
        if n.get("description"):
            node["desc"] = n["description"][:300]
        if n.get("position") is not None:
            node["pos"] = n["position"]
        if n.get("printedPageNumber"):
            node["printed"] = n["printedPageNumber"]
        if n.get("onPage"):
            node["page"] = int(short(n["onPage"]).split("/")[-1])
        if n.get("chartData") is not None:
            cd = n["chartData"]
            series = cd if isinstance(cd, list) else [cd]
            pts = sum(len(s.get("data", [])) for s in series if isinstance(s, dict))
            node["chart"] = {"charts": len(series), "points": pts}
        if n.get("contains"):
            node["c"] = [short(c) for c in n["contains"]]
        if n.get("supplement"):
            node["supp"] = [short(s) for s in n["supplement"]]
        if n.get("region"):
            boxes = []
            for r in n["region"]:
                m = re.match(r"xywh=(\d+),(\d+),(\d+),(\d+)", r["hasSelector"]["value"])
                if m:
                    boxes.append([int(v) for v in m.groups()])
            if boxes:
                node["bbox"] = boxes
        if n.get("pax:level"):
            node["level"] = n["pax:level"]
        out[short(iri)] = node

    for n in graph.values():
        if n.get("pageImageWidth"):
            page_w, page_h = n["pageImageWidth"], n["pageImageHeight"]
            break
    return {"pageW": page_w, "pageH": page_h, "nodes": out, "root": ""}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    repo = Path(__file__).resolve().parent.parent
    ap.add_argument("--jsonld", type=Path, default=repo / "examples" / "Mercadier2011.jsonld")
    ap.add_argument("--html", type=Path, default=repo / "docs" / "explorer" / "index.html")
    ap.add_argument("--page-w", type=int, default=1241)
    ap.add_argument("--page-h", type=int, default=1648)
    args = ap.parse_args()

    data = compact(args.jsonld, args.page_w, args.page_h)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    html = args.html.read_text()
    new_html, count = re.subn(r"^const KG = .*;$", f"const KG = {payload};",
                              html, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"expected exactly one `const KG = ...;` line in {args.html}, found {count}")
    args.html.write_text(new_html)
    print(f"Injected {len(payload) // 1024} KB ({len(data['nodes'])} nodes) into {args.html}")


if __name__ == "__main__":
    main()
