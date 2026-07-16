#!/usr/bin/env python3
"""Adapter: paper-atomizer `processed_document.json` → PAX JSON-LD.

This is the proof that the graph is pipeline-independent: a second, independently
evolved pipeline (crcresearch/paper-atomizer — flat elements, `{x,y,width,height}`
boxes, string ids, nested section tree) targets the SAME graph shape as the
deepseek-ocr-experiments exporter, so the evaluation engine can diff their outputs.

Graphs are BUILT through the LinkML-generated Pydantic models (linkml/generated/),
so a malformed graph fails at construction rather than at SHACL time; the models
are then serialized back to compacted JSON-LD (the inverse of the shim documented
in linkml/FINDINGS.md).

Schema differences handled here (paper-atomizer → PAX):
  sections nested via `children`     → flattened, containment via po:contains
  `matter_type` / `level`            → pax:matter / pax:level
  elements carry `section_id`        → sections contain their elements
  `bounding_box {x,y,width,height}`  → xywh= media-fragment selector
  figure `caption` field AND separate `image_caption` elements with `parent_id`
                                     → doco:FigureBox / doco:TableBox grouping
  `page_dimensions[page]`            → pax:pageImageWidth/Height
  string ids ("el-1", "sec-1")       → run-scoped IRIs
  no printed page numbers            → pax:printedPageLabel simply absent

Usage:
    python3 adapters/paper_atomizer.py <processed_document.json> -o out.jsonld \\
        --paper-id <slug> [--base-iri https://w3id.org/alexandria/paper] \\
        [--run-id <id>] [--doi <doi>]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "linkml" / "generated"))
import pax_instance as M  # noqa: E402

DEFAULT_BASE = "https://w3id.org/alexandria/paper"

ELEMENT_TYPE_MAP = {
    "text": "doco:Paragraph",
    "title": "doco:Title",
    "sub_title": "doco:SectionTitle",
    "image": "doco:Figure",
    "image_caption": "deo:Caption",
    "table": "doco:Table",
    "table_caption": "deo:Caption",
    "table_footnote": "doco:Footnote",
    "formula": "doco:Formula",
    "equation": "doco:Formula",
    "footnote": "doco:Footnote",
    "list": "doco:List",
    "header": "pax:PageHeader",
    "footer": "pax:PageFooter",
    "page_number": "pax:PageNumberMark",
    "code": "pax:CodeBlock",
    "other": "pax:OtherElement",
}

FIGURE_TYPE_CONCEPTS = {
    "bar_chart": "pax:barChart", "line_graph": "pax:lineGraph",
    "scatter_plot": "pax:scatterPlot", "histogram": "pax:histogramFigure",
    "heatmap": "pax:heatmapFigure", "boxplot": "pax:boxplotFigure",
    "pie_chart": "pax:pieChart", "photograph": "pax:photograph",
    "micrograph": "pax:micrograph", "diagram": "pax:diagramFigure",
    "flowchart": "pax:flowchartFigure", "schematic": "pax:schematicFigure",
    "map": "pax:mapFigure", "other": "pax:otherFigureType",
}

SECTION_NAME_TYPES = [
    (("abstract",), "doco:Abstract"),
    (("introduction",), "deo:Introduction"),
    (("materials and methods", "methods"), "deo:Methods"),
    (("materials",), "deo:Materials"),
    (("results",), "deo:Results"),
    (("discussion",), "deo:Discussion"),
    (("conclusion", "conclusions"), "deo:Conclusion"),
    (("acknowledgements", "acknowledgments"), "deo:Acknowledgements"),
    (("related work",), "deo:RelatedWork"),
    (("background",), "deo:Background"),
    (("references", "bibliography"), "doco:Bibliography"),
    (("supporting information", "supplementary information", "supplementary material"),
     "deo:SupplementaryInformationDescription"),
]

MATTER_TYPE = {"front": "doco:FrontMatter", "body": "doco:BodyMatter", "back": "doco:BackMatter"}

# paper-atomizer's own pipeline (docs/pipeline_overview.md of that repo)
AGENT_SPECS = [
    ("deepseek-ocr", "DeepSeek-OCR", "deepseek-ai/DeepSeek-OCR",
     "OCR, layout detection, element bounding boxes"),
    ("heading-classifier", "Heading classifier", "paper-atomizer heading classification",
     "Section hierarchy: matter + level"),
    ("figure-classifier", "Figure classifier", "paper-atomizer figure classification",
     "Figure type + description"),
    ("chart-extractor", "Chart extractor", "paper-atomizer chart extraction",
     "Chart data extraction"),
]


def section_extra_types(name):
    low = (name or "").strip().lower()
    # strip leading numbering ("1. Introduction" -> "introduction")
    while low and (low[0].isdigit() or low[0] in ". "):
        low = low[1:]
    return [t for keys, t in SECTION_NAME_TYPES if low in keys]


def flatten(sections, out=None):
    """paper-atomizer nests sections via `children`; PAX wants them addressable."""
    out = [] if out is None else out
    for s in sections or []:
        out.append(s)
        flatten(s.get("children"), out)
    return out


def region_of(el, page_image_iri):
    box = el.get("bounding_box")
    if not box:
        return None
    x, y = int(box["x"]), int(box["y"])
    w, h = int(box["width"]), int(box["height"])
    if w <= 0 or h <= 0:
        return None
    return M.Region(
        id=f"_:region-{el['id']}", category=["oa:ResourceSelection"],
        hasSource=page_image_iri,
        hasSelector=M.FragmentSelector(
            id=f"_:selector-{el['id']}", category=["oa:FragmentSelector"],
            value=f"xywh={x},{y},{w},{h}",
            conformsTo="http://www.w3.org/TR/media-frags/"))


# ---------------------------------------------------------------- serialization

SHIM_KEYS = {"id": "@id", "category": "@type"}
# terms the published context defines no shortcut for — emitted as prefixed CURIEs
PREFIXED = {"level", "matter", "pageStart", "pageEnd", "parsedContent"}


def dump(model) -> dict:
    """Pydantic model -> compacted JSON-LD node (inverse of the FINDINGS shim)."""
    raw = model.model_dump(exclude_none=True, exclude_defaults=False)
    out = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            v = {SHIM_KEYS.get(kk, kk): vv for kk, vv in v.items()}
        key = SHIM_KEYS.get(k, f"pax:{k}" if k in PREFIXED else k)
        out[key] = v
    if str(out.get("@id", "")).startswith("_:"):
        out.pop("@id")  # blank nodes: ids were synthesized for LinkML identifiers
    return out


def dump_region(r: "M.Region") -> dict:
    sel = r.hasSelector
    return {"@type": "oa:ResourceSelection", "hasSource": r.hasSource,
            "hasSelector": {"@type": "oa:FragmentSelector", "value": sel.value,
                            "conformsTo": sel.conformsTo}}


def convert(doc: dict, paper_id: str, base: str, run_id: str, doi=None) -> dict:
    entity_base = f"{base}/{paper_id}"
    gen_base = f"{entity_base}/run/{run_id}"
    manifestation_iri = f"{entity_base}/manifestation/pdf"
    nodes = []

    # ---- pages (paper-atomizer gives real page dimensions; PAX wants them) ----
    dims = doc.get("page_dimensions") or {}
    n_pages = int(doc.get("total_pages") or len(dims) or 0)
    page_iri = {}
    for seq in range(1, n_pages + 1):
        d = dims.get(str(seq)) or dims.get(seq) or {}
        page_iri[seq] = f"{gen_base}/page/{seq}"
        nodes.append(M.Page(
            id=page_iri[seq], category=["fabio:Page"], position=seq,
            image=f"{gen_base}/asset/page_images/page_{seq:03d}.png",
            pageImageWidth=d.get("width"), pageImageHeight=d.get("height")))

    # ---- elements ----
    elements = doc.get("elements") or []
    elem_iri, elem_by_id, caption_of = {}, {}, {}
    for el in elements:
        if el.get("parent_id"):           # a caption/footnote attached to a body element
            caption_of.setdefault(el["parent_id"], []).append(el["id"])
        elem_by_id[el["id"]] = el

    order = 0
    for el in elements:
        order += 1
        seq = int(el.get("page_number") or 0)
        eid = f"{gen_base}/element/{el['id']}"
        elem_iri[el["id"]] = eid
        rtype = ELEMENT_TYPE_MAP.get(el.get("type"), "pax:OtherElement")
        region = region_of(el, f"{gen_base}/asset/page_images/page_{seq:03d}.png")
        node = M.DocumentElement(
            id=eid, category=[rtype], position=order,
            onPage=page_iri.get(seq),
            region=[region] if region else None,
            text=el.get("content") or None,
            description=el.get("figure_description") or None,
            rawType=el["type"] if rtype == "pax:OtherElement" else None)
        if el.get("figure_type"):
            node.figureType = FIGURE_TYPE_CONCEPTS.get(el["figure_type"], "pax:otherFigureType")
        if el.get("chart_data") is not None:
            node.chartData = el["chart_data"]
        nodes.append(node)

    # ---- boxes: figure/table + its caption (the DoCO box pattern) ----
    box_iri, boxed = {}, set()
    for parent, kids in caption_of.items():
        if parent not in elem_by_id:
            continue
        kind = "doco:TableBox" if elem_by_id[parent].get("type") == "table" else "doco:FigureBox"
        members = [elem_iri[parent]] + [elem_iri[k] for k in kids if k in elem_iri]
        if len(members) < 2:
            continue
        biri = f"{gen_base}/box/{parent}"
        box_iri[parent] = biri
        boxed.update([parent] + kids)
        nodes.append(M.Box(id=biri, category=[kind], contains=members, hasPart=members))

    # ---- sections (flattened; containment rebuilt from parent_id + section_id) ----
    flat = flatten(doc.get("sections"))
    sec_iri = {s["id"]: f"{gen_base}/section/{s['id']}" for s in flat}
    sec_children = {s["id"]: [c["id"] for c in (s.get("children") or [])] for s in flat}
    els_of_section = {}
    for el in elements:
        if el.get("section_id") and el["id"] not in boxed:
            els_of_section.setdefault(el["section_id"], []).append(elem_iri[el["id"]])
        elif el.get("section_id") and el["id"] in box_iri:
            els_of_section.setdefault(el["section_id"], []).append(box_iri[el["id"]])

    # paper-atomizer wraps the whole paper in one title-level section; PAX groups
    # sections by matter instead (the wrapper keeps only its own elements — its
    # children are re-parented to the matter containers, never contained twice).
    by_id = {s["id"]: s for s in flat}
    wrappers = {s["id"] for s in flat if s.get("level") == "title"}
    promoted = {s["id"] for s in flat
                if (s.get("parent_id") in wrappers) or
                   (not s.get("parent_id") and s["id"] not in wrappers)}

    # pax:pageStart/pageEnd are materialized from ACTUAL containment (the same
    # convention the reference exporter adopted after the SHACL projection check
    # caught real undercounting) — otherwise the graph contradicts itself and the
    # two producers' graphs would not be comparable. Where paper-atomizer's own
    # claim disagrees, that is a finding about the pipeline: counted and reported,
    # never silently swallowed.
    el_page = {el["id"]: int(el.get("page_number") or 0) for el in elements}

    def span(sid, seen=None):
        seen = seen or set()
        if sid in seen:
            return []
        seen.add(sid)
        pages = [el_page[e["id"]] for e in elements
                 if e.get("section_id") == sid and el_page[e["id"]]]
        for c in sec_children.get(sid, []):
            pages += span(c, seen)
        return pages

    corrections = []
    for s in flat:
        kids = [c for c in sec_children[s["id"]] if c not in promoted]
        contains = [sec_iri[c] for c in kids] + els_of_section.get(s["id"], [])
        pages = span(s["id"])
        p_start, p_end = (min(pages), max(pages)) if pages else \
                         (s.get("page_start"), s.get("page_end"))
        if pages and (p_start, p_end) != (s.get("page_start"), s.get("page_end")):
            corrections.append((s["id"], s.get("name"),
                                (s.get("page_start"), s.get("page_end")), (p_start, p_end)))
        nodes.append(M.Section(
            id=sec_iri[s["id"]], category=["doco:Section"] + section_extra_types(s.get("name")),
            title=s.get("name"), level=s.get("level"), matter=s.get("matter_type"),
            pageStart=p_start, pageEnd=p_end,
            contains=contains or None))

    # ---- matter containers ----
    matter_nodes = []
    for matter, cls in MATTER_TYPE.items():
        tops = [sec_iri[sid] for sid in
                [s["id"] for s in flat
                 if s["id"] in promoted and s.get("matter_type") == matter]]
        # the title wrapper itself belongs to its own matter, at the top level
        tops += [sec_iri[s["id"]] for s in flat
                 if s["id"] in wrappers and not s.get("parent_id")
                 and s.get("matter_type") == matter]
        if tops:
            iri = f"{gen_base}/{matter}-matter"
            matter_nodes.append(iri)
            nodes.append(M.Matter(id=iri, category=[cls], contains=tops))

    # ---- provenance ----
    activity_iri = f"{gen_base}/prov/activity"
    agents = []
    for slug, name, version, desc in AGENT_SPECS:
        airi = f"{gen_base}/prov/agent/{slug}"
        agents.append(airi)
        nodes.append(M.SoftwareAgent(id=airi, category=["prov:SoftwareAgent"],
                                     name=name, softwareVersion=version, description=desc))
    nodes.append(M.Activity(
        id=activity_iri, category=["prov:Activity"],
        name="paper-atomizer pipeline run", used=manifestation_iri,
        softwareVersion=f"paper-atomizer@{doc.get('paper_id', 'unknown')}",
        wasAssociatedWith=agents))
    nodes.append(M.Dataset(
        id=gen_base, category=["schema:Dataset", "prov:Entity"],
        name="Extracted document-structure knowledge graph",
        license="https://creativecommons.org/licenses/by/4.0/",
        about=entity_base, wasDerivedFrom=[manifestation_iri],
        wasGeneratedBy=[activity_iri]))

    # ---- manifestation + expression root ----
    nodes.append(M.Manifestation(
        id=manifestation_iri, category=["fabio:DigitalManifestation"],
        name="PDF", embodimentOf=entity_base,
        part=[page_iri[s] for s in sorted(page_iri)]))
    root = M.PaperExpression(
        id=entity_base, category=["fabio:JournalArticle", "schema:ScholarlyArticle"],
        title=doc.get("title") or None, identifier=doi,
        pageCount=n_pages or None, embodiment=manifestation_iri,
        contains=matter_nodes or None)

    graph = [dump_node(root)] + [dump_node(n) for n in nodes]
    return ({"@context": "https://w3id.org/paper-anatomy/context.jsonld", "@graph": graph},
            corrections)


def dump_node(model) -> dict:
    out = dump(model)
    if "region" in out:
        out["region"] = [dump_region(r) for r in model.region]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=Path, help="paper-atomizer processed_document.json")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--paper-id", required=True)
    ap.add_argument("--base-iri", default=DEFAULT_BASE)
    ap.add_argument("--run-id", default=None, help="defaults to the paper-atomizer paper_id")
    ap.add_argument("--doi", default=None)
    args = ap.parse_args()

    doc = json.loads(args.input.read_text())
    run_id = args.run_id or str(doc.get("paper_id", "run"))[:8]
    kg, corrections = convert(doc, args.paper_id, args.base_iri, run_id, args.doi)
    args.output.write_text(json.dumps(kg, indent=2, ensure_ascii=False))
    print(f"Wrote {len(kg['@graph'])} nodes → {args.output}")
    if corrections:
        print(f"\n{len(corrections)} section page-range(s) materialized from containment "
              f"(paper-atomizer's own claim disagreed):")
        for sid, name, claimed, actual in corrections[:10]:
            print(f"  {sid:8s} {str(name)[:44]:46s} claimed {claimed} → {actual}")
        if len(corrections) > 10:
            print(f"  … and {len(corrections) - 10} more")


if __name__ == "__main__":
    main()
