#!/usr/bin/env python3
"""Tests for the paper-atomizer adapter, on a synthetic input that reproduces the
schema quirks found in real data (nested sections under one title wrapper,
`{x,y,width,height}` boxes, string ids, caption via `parent_id`, page ranges that
disagree with the elements' own pages).

Every check is a contract the adapter must keep; each was observed failing
against the pre-fix adapter (see the git history: double-containment and
page-range materialization).

Run:  uv run --with pydantic python adapters/test_paper_atomizer.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paper_atomizer import convert  # noqa: E402

failures = []


def check(ok, msg):
    print(("  ✓ " if ok else "  ✗ ") + msg)
    if not ok:
        failures.append(msg)


DOC = {
    "paper_id": "test-run", "title": "A Test Paper", "total_pages": 2,
    "page_dimensions": {"1": {"width": 1275, "height": 1650},
                        "2": {"width": 1275, "height": 1650}},
    "sections": [{
        "id": "sec-1", "name": "A Test Paper", "matter_type": "front", "level": "title",
        "page_start": 1, "page_end": 2, "parent_id": None,
        "children": [
            {"id": "sec-2", "name": "ABSTRACT", "matter_type": "front", "level": "section",
             "page_start": 1, "page_end": 1, "parent_id": "sec-1", "children": []},
            # claims page 1 only, but its elements are on pages 1 AND 2
            {"id": "sec-3", "name": "1. Introduction", "matter_type": "body",
             "level": "section", "page_start": 1, "page_end": 1, "parent_id": "sec-1",
             "children": [
                 {"id": "sec-4", "name": "1.1. Scope", "matter_type": "body",
                  "level": "subsection", "page_start": 2, "page_end": 2,
                  "parent_id": "sec-3", "children": []}]},
            {"id": "sec-5", "name": "References", "matter_type": "back", "level": "section",
             "page_start": 2, "page_end": 2, "parent_id": "sec-1", "children": []},
        ]}],
    "elements": [
        {"id": "el-1", "type": "title", "page_number": 1, "section_id": "sec-1",
         "bounding_box": {"x": 100, "y": 100, "width": 500, "height": 40},
         "content": "A Test Paper"},
        {"id": "el-2", "type": "text", "page_number": 1, "section_id": "sec-2",
         "bounding_box": {"x": 100, "y": 200, "width": 400, "height": 80},
         "content": "Abstract text."},
        # sec-3 starts on page 1 and continues on page 2 — its own claim (1,1)
        # is wrong, exactly the pattern seen in real paper-atomizer output
        {"id": "el-3", "type": "text", "page_number": 1, "section_id": "sec-3",
         "bounding_box": {"x": 100, "y": 300, "width": 400, "height": 60},
         "content": "Intro paragraph starting on page 1."},
        {"id": "el-3b", "type": "text", "page_number": 2, "section_id": "sec-3",
         "bounding_box": {"x": 100, "y": 100, "width": 400, "height": 60},
         "content": "…continuing on page 2."},
        {"id": "el-4", "type": "image", "page_number": 2, "section_id": "sec-4",
         "bounding_box": {"x": 100, "y": 400, "width": 300, "height": 200},
         "figure_type": "line_graph", "figure_description": "A line graph.",
         "chart_data": [{"chart_title": "T", "data": [{"series": "s", "x": 1, "y": 2}]}]},
        {"id": "el-5", "type": "image_caption", "page_number": 2, "section_id": "sec-4",
         "parent_id": "el-4", "bounding_box": {"x": 100, "y": 610, "width": 300, "height": 30},
         "content": "Fig. 1. A caption."},
    ],
}


def main():
    kg, corrections = convert(DOC, "test-paper", "https://w3id.org/alexandria/paper", "r1")
    nodes = {n["@id"]: n for n in kg["@graph"]}
    E = "https://w3id.org/alexandria/paper/test-paper"
    G = f"{E}/run/r1"

    print("[1] graph shape")
    root = nodes.get(E)
    check(root and "fabio:JournalArticle" in root["@type"], "Expression root minted at the paper IRI")
    check(root and root.get("pageCount") == 2 and root.get("title") == "A Test Paper",
          "root carries title + page count")
    check(f"{G}/prov/activity" in nodes and nodes[G].get("license"),
          "dataset node carries the license; activity present")
    check(nodes[G].get("about") == E and "prov:used" not in nodes[G],
          "provenance on the dataset (prov:used stays on the activity)")

    print("[2] no double containment (the SHACL 'recommended' profile caught this)")
    parents = {}
    for n in kg["@graph"]:
        for c in n.get("contains", []) or []:
            parents.setdefault(c, []).append(n["@id"])
    dupes = {k: v for k, v in parents.items() if len(v) > 1}
    check(not dupes, f"every node has one container ({len(dupes)} with several)")
    body = nodes.get(f"{G}/body-matter")
    check(body and f"{G}/section/sec-3" in body["contains"],
          "body section re-parented from the title wrapper to body-matter")
    wrapper = nodes[f"{G}/section/sec-1"]
    check(f"{G}/section/sec-3" not in (wrapper.get("contains") or []),
          "the title wrapper no longer contains the promoted section")

    print("[3] page ranges materialized from containment, disagreements reported")
    intro = nodes[f"{G}/section/sec-3"]
    check((intro["pax:pageStart"], intro["pax:pageEnd"]) == (1, 2),
          f"claimed (1,1) → materialized {(intro['pax:pageStart'], intro['pax:pageEnd'])} "
          "(elements sit on pages 1 and 2 via its subsection)")
    check(any(c[0] == "sec-3" for c in corrections),
          f"the disagreement is reported, not swallowed ({len(corrections)} correction(s))")

    print("[4] boxes, regions, chart payload")
    box = nodes.get(f"{G}/box/el-4")
    check(box and set(box["contains"]) == {f"{G}/element/el-4", f"{G}/element/el-5"},
          "FigureBox groups the figure and its caption")
    check(box and box.get("hasPart") == box.get("contains"),
          "box asserts dcterms:hasPart alongside po:contains")
    fig = nodes[f"{G}/element/el-4"]
    check(fig.get("figureType") == "pax:lineGraph", "figure type mapped to the SKOS concept")
    src_fig = next(e for e in DOC["elements"] if e["id"] == "el-4")
    check(fig.get("chartData") == src_fig["chart_data"], "chart payload passed through")
    sel = fig["region"][0]["hasSelector"]
    check(sel["value"] == "xywh=100,400,300,200",
          f"{{x,y,width,height}} → media fragment ({sel['value']})")
    page2 = nodes[f"{G}/page/2"]
    check(page2.get("pageImageWidth") == 1275 and page2.get("pageImageHeight") == 1650,
          "page declares its pixel space (required for cross-resolution IoU)")

    print("[5] rhetorical typing")
    check("deo:Introduction" in nodes[f"{G}/section/sec-3"]["@type"],
          "'1. Introduction' → deo:Introduction (numbering stripped)")
    check("doco:Bibliography" in nodes[f"{G}/section/sec-5"]["@type"],
          "'References' → doco:Bibliography")

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        sys.exit(1)
    print("ALL ADAPTER TESTS PASSED")


if __name__ == "__main__":
    main()
