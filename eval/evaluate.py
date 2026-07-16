#!/usr/bin/env python3
"""PAX evaluation engine — graph-diff a candidate paper-structure KG against a reference.

Both inputs are PAX JSON-LD documents (compacted with the shared context.jsonld),
so the comparison is schema-free: instance IRIs are never compared, only structure.
Each metric is grounded in a competency question (COMPETENCY_QUESTIONS.md, CQ12).

Metrics (the seven from the vocabulary README):
  1. detection        precision/recall of elements, matched by (page, type, IoU >= t)
  2. localization     mean IoU over matched elements
  3. reading_order    Kendall-tau between the matched elements' position sequences
  4. hierarchy        Zhang-Shasha tree edit distance between the section trees
  5. rhetorical       accuracy of deo:*/matter/level on title-matched sections
  6. caption_linking  precision/recall of figure/table->caption box membership edges
  7. chart_data       pax:chartData payload diff (chart/row counts, aligned value MAE)

Conformance (SHACL) is validate.py's job; scoring tolerances live HERE, not in shapes.

Usage:
    python3 eval/evaluate.py reference.jsonld candidate.jsonld [-o report.json] [--iou 0.5]
"""

import argparse
import json
import re
import sys
from pathlib import Path

STRUCTURAL_PREFIXES = ("doco:", "deo:", "pax:")
MATTERS = ("doco:FrontMatter", "doco:BodyMatter", "doco:BackMatter")


# ---------------------------------------------------------------- graph access

def types_of(node) -> list:
    t = node.get("@type", [])
    return [t] if isinstance(t, str) else list(t)


def load(path: Path) -> dict:
    kg = json.loads(Path(path).read_text())
    return {n["@id"]: n for n in kg["@graph"]}


def page_positions(nodes: dict) -> dict:
    """page IRI -> file-sequence position."""
    return {i: n["position"] for i, n in nodes.items()
            if "fabio:Page" in types_of(n) and "position" in n}


def primary_type(node) -> str:
    """The structural type used for matching (first doco:/deo:/pax: type)."""
    for t in types_of(node):
        if t.startswith(STRUCTURAL_PREFIXES) and t not in MATTERS:
            return t
    return (types_of(node) or ["?"])[0]


def bbox_of(node):
    for r in node.get("region", []):
        m = re.match(r"xywh=(\d+),(\d+),(\d+),(\d+)", r.get("hasSelector", {}).get("value", ""))
        if m:
            return tuple(int(v) for v in m.groups())
    return None


def elements(nodes: dict) -> dict:
    """Document elements: everything with a reading-order position on a page
    (the DocumentElementShape contract). Returns id -> descriptor."""
    pages = page_positions(nodes)
    out = {}
    for i, n in nodes.items():
        if "position" in n and n.get("onPage") in pages:
            out[i] = {"type": primary_type(n), "page": pages[n["onPage"]],
                      "pos": n["position"], "bbox": bbox_of(n), "node": n}
    return out


def iou(a, b) -> float:
    if not a or not b:
        return 0.0
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


# ---------------------------------------------------------------- matching

def match_elements(ref: dict, cand: dict, threshold: float):
    """Greedy IoU matching within (page, type) groups. Returns ref_id -> cand_id."""
    groups = {}
    for cid, c in cand.items():
        groups.setdefault((c["page"], c["type"]), []).append(cid)
    matches, used = {}, set()
    for rid, r in sorted(ref.items(), key=lambda kv: kv[1]["pos"]):
        best, best_iou = None, 0.0
        for cid in groups.get((r["page"], r["type"]), []):
            if cid in used:
                continue
            v = iou(r["bbox"], cand[cid]["bbox"])
            if v > best_iou:
                best, best_iou = cid, v
        if best is not None and best_iou >= threshold:
            matches[rid] = best
            used.add(best)
    return matches


def prf(n_match: int, n_cand: int, n_ref: int) -> dict:
    p = n_match / n_cand if n_cand else None
    r = n_match / n_ref if n_ref else None
    f = (2 * p * r / (p + r)) if p and r and (p + r) else (0.0 if p is not None and r is not None else None)
    return {"precision": p, "recall": r, "f1": f}


# ---------------------------------------------------------------- metric 3: reading order

def kendall_tau(seq_a: list, seq_b: list):
    """tau-a over two equally-indexed sequences (matched pairs)."""
    n = len(seq_a)
    if n < 2:
        return None
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (seq_a[i] - seq_a[j]) * (seq_b[i] - seq_b[j])
            if s > 0:
                concordant += 1
            elif s < 0:
                discordant += 1
    return (concordant - discordant) / (n * (n - 1) / 2)


# ---------------------------------------------------------------- metric 4: section tree

def norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def section_tree(nodes: dict):
    """Ordered tree of sections: (label, [children]) under a synthetic root.
    Top level follows front/body/back matter order; nesting follows po:contains order."""
    sections = {i for i, n in nodes.items() if "doco:Section" in types_of(n)}

    def build(sec_id):
        n = nodes[sec_id]
        kids = [build(c) for c in n.get("contains", []) if c in sections]
        return (norm_title(n.get("title", "")), kids)

    top = []
    matters = [i for i, n in nodes.items() if any(m in types_of(n) for m in MATTERS)]
    order = {m: k for k, m in enumerate(MATTERS)}
    matters.sort(key=lambda i: min(order[t] for t in types_of(nodes[i]) if t in order))
    for m in matters:
        for c in nodes[m].get("contains", []):
            if c in sections:
                top.append(build(c))
    return ("", top)


def tree_size(t) -> int:
    return 1 + sum(tree_size(c) for c in t[1])


def zss_distance(t1, t2) -> int:
    """Zhang–Shasha ordered tree edit distance, unit costs."""
    def index(t):
        nodes, lmds = [], []
        def walk(n):
            start = len(nodes)  # post-order index the first node of this subtree gets
            for c in n[1]:
                walk(c)
            nodes.append(n[0])
            # leftmost leaf descendant: a leaf is its own; an inner node inherits
            # its first child's (which sits at post-order index `start`)
            lmds.append(len(nodes) - 1 if not n[1] else lmds[start])
        walk(t)
        keyroots = [i for i in range(len(nodes))
                    if all(lmds[j] != lmds[i] for j in range(i + 1, len(nodes)))]
        return nodes, lmds, keyroots

    l1, lmd1, kr1 = index(t1)
    l2, lmd2, kr2 = index(t2)
    td = [[0] * len(l2) for _ in l1]

    def treedist(i, j):
        m, n = i - lmd1[i] + 2, j - lmd2[j] + 2
        fd = [[0] * n for _ in range(m)]
        ioff, joff = lmd1[i] - 1, lmd2[j] - 1
        for x in range(1, m):
            fd[x][0] = fd[x - 1][0] + 1
        for y in range(1, n):
            fd[0][y] = fd[0][y - 1] + 1
        for x in range(1, m):
            for y in range(1, n):
                if lmd1[x + ioff] == lmd1[i] and lmd2[y + joff] == lmd2[j]:
                    cost = 0 if l1[x + ioff] == l2[y + joff] else 1
                    fd[x][y] = min(fd[x - 1][y] + 1, fd[x][y - 1] + 1, fd[x - 1][y - 1] + cost)
                    td[x + ioff][y + joff] = fd[x][y]
                else:
                    p, q = lmd1[x + ioff] - 1 - ioff, lmd2[y + joff] - 1 - joff
                    fd[x][y] = min(fd[x - 1][y] + 1, fd[x][y - 1] + 1,
                                   fd[p][q] + td[x + ioff][y + joff])
        return fd[m - 1][n - 1]

    for i in kr1:
        for j in kr2:
            treedist(i, j)
    return td[len(l1) - 1][len(l2) - 1]


# ---------------------------------------------------------------- metric 5: rhetorical

def pget(node, term):
    """Read a pax term that exporters may emit either as a context shortcut
    ('matter') or as a prefixed CURIE key ('pax:matter') — both are valid
    compactions; the shipped context defines no shortcut for these, so the
    prefixed form is what real data carries."""
    return node.get(term, node.get(f"pax:{term}"))


def sections_by_title(nodes: dict) -> dict:
    out = {}
    for i, n in nodes.items():
        if "doco:Section" in types_of(n) and n.get("title"):
            out.setdefault(norm_title(n["title"]), n)
    return out


def role_set(node) -> frozenset:
    return frozenset(t for t in types_of(node) if t != "doco:Section")


# ---------------------------------------------------------------- metric 6: caption links

def caption_links(nodes: dict) -> set:
    links = set()
    for i, n in nodes.items():
        if not {"doco:FigureBox", "doco:TableBox"} & set(types_of(n)):
            continue
        kids = n.get("contains", [])
        bodies = [k for k in kids if k in nodes
                  and {"doco:Figure", "doco:Table"} & set(types_of(nodes[k]))]
        caps = [k for k in kids if k in nodes and "deo:Caption" in types_of(nodes[k])]
        for b in bodies:
            for c in caps:
                links.add((b, c))
    return links


# ---------------------------------------------------------------- metric 7: chart data

def chart_payload(node):
    cd = node.get("chartData")
    if cd is None:
        return None
    v = cd.get("@value") if isinstance(cd, dict) and "@value" in cd else cd
    if isinstance(v, str):
        v = json.loads(v)
    charts = [c for c in (v if isinstance(v, list) else [v]) if isinstance(c, dict)]
    return charts


def chart_series(charts) -> dict:
    """(series, x) -> y for every numeric point.

    Real payloads come in two shapes (both occur in the shipped example):
    scalar rows ({series, x: 0.6, y: 12000}) and vector rows where one row is
    a whole series ({series, x: [La, Ce, …], y: [8000, 18000, …]}). Rows with
    no numeric y (extraction found none) contribute nothing.
    """
    pts = {}
    for c in charts:
        for row in c.get("data") or []:
            if not isinstance(row, dict):
                continue
            s, x, y = str(row.get("series")), row.get("x"), row.get("y")
            if isinstance(y, list):
                xs = x if isinstance(x, list) and len(x) == len(y) else range(len(y))
                for xi, yi in zip(xs, y):
                    if isinstance(yi, (int, float)):
                        pts[(s, str(xi))] = float(yi)
            elif isinstance(y, (int, float)):
                pts[(s, str(x))] = float(y)
    return pts


def compare_charts(ref_node, cand_node) -> dict:
    r, c = chart_payload(ref_node), chart_payload(cand_node)
    out = {"ref_charts": len(r) if r else 0, "cand_charts": len(c) if c else 0,
           "ref_rows": sum(len(x.get("data") or []) for x in r or []),
           "cand_rows": sum(len(x.get("data") or []) for x in c or [])}
    rp, cp = chart_series(r or []), chart_series(c or [])
    aligned = set(rp) & set(cp)
    out["aligned_points"] = len(aligned)
    out["value_mae"] = (sum(abs(rp[k] - cp[k]) for k in aligned) / len(aligned)) if aligned else None
    return out


# ---------------------------------------------------------------- driver

def evaluate(ref_path: Path, cand_path: Path, threshold: float = 0.5) -> dict:
    ref_nodes, cand_nodes = load(ref_path), load(cand_path)
    ref_el, cand_el = elements(ref_nodes), elements(cand_nodes)
    matches = match_elements(ref_el, cand_el, threshold)

    # 1. detection (+ geometry-free presence as a secondary view)
    per_type = {}
    for t in sorted({e["type"] for e in list(ref_el.values()) + list(cand_el.values())}):
        nm = sum(1 for r, c in matches.items() if ref_el[r]["type"] == t)
        per_type[t] = prf(nm, sum(1 for e in cand_el.values() if e["type"] == t),
                          sum(1 for e in ref_el.values() if e["type"] == t))
    detection = prf(len(matches), len(cand_el), len(ref_el))
    detection.update({"matched": len(matches), "ref_elements": len(ref_el),
                      "cand_elements": len(cand_el), "per_type": per_type})

    ref_pres = sorted((e["type"], e["page"]) for e in ref_el.values())
    cand_pres = sorted((e["type"], e["page"]) for e in cand_el.values())
    common = 0
    pool = list(cand_pres)
    for x in ref_pres:
        if x in pool:
            pool.remove(x)
            common += 1
    presence = prf(common, len(cand_pres), len(ref_pres))

    # 2. localization
    ious = [iou(ref_el[r]["bbox"], cand_el[c]["bbox"]) for r, c in matches.items()]
    localization = {"mean_iou": sum(ious) / len(ious) if ious else None, "pairs": len(ious)}

    # 3. reading order
    pairs = sorted(matches.items(), key=lambda rc: ref_el[rc[0]]["pos"])
    tau = kendall_tau([ref_el[r]["pos"] for r, _ in pairs],
                      [cand_el[c]["pos"] for _, c in pairs])
    reading_order = {"kendall_tau": tau, "pairs": len(pairs)}

    # 4. hierarchy
    t1, t2 = section_tree(ref_nodes), section_tree(cand_nodes)
    dist = zss_distance(t1, t2)
    denom = max(tree_size(t1), tree_size(t2))
    hierarchy = {"tree_edit_distance": dist, "ref_sections": tree_size(t1) - 1,
                 "cand_sections": tree_size(t2) - 1,
                 "similarity": 1 - dist / denom if denom else None}

    # 5. rhetorical
    rs, cs = sections_by_title(ref_nodes), sections_by_title(cand_nodes)
    shared = sorted(set(rs) & set(cs))
    role_ok = sum(1 for k in shared if role_set(rs[k]) == role_set(cs[k]))
    matter_ok = sum(1 for k in shared if pget(rs[k], "matter") == pget(cs[k], "matter"))
    level_ok = sum(1 for k in shared if pget(rs[k], "level") == pget(cs[k], "level"))
    n = len(shared)
    rhetorical = {"sections_compared": n,
                  "role_accuracy": role_ok / n if n else None,
                  "matter_accuracy": matter_ok / n if n else None,
                  "level_accuracy": level_ok / n if n else None,
                  # vacuousness guards: how many compared sections carry real values
                  "sections_with_matter": sum(1 for k in shared if pget(rs[k], "matter") is not None),
                  "sections_with_level": sum(1 for k in shared if pget(rs[k], "level") is not None)}

    # 6. caption linking
    ref_links, cand_links = caption_links(ref_nodes), caption_links(cand_nodes)
    recovered = sum(1 for f, cap in ref_links
                    if (matches.get(f), matches.get(cap)) in cand_links)
    linking = prf(recovered, len(cand_links), len(ref_links))
    linking.update({"ref_links": len(ref_links), "cand_links": len(cand_links)})

    # 7. chart data
    figs = []
    for rid, cid in matches.items():
        if chart_payload(ref_el[rid]["node"]) is not None or \
           chart_payload(cand_el[cid]["node"]) is not None:
            figs.append(compare_charts(ref_el[rid]["node"], cand_el[cid]["node"]))
    aligned = [f for f in figs if f["value_mae"] is not None]
    chart = {"figures_compared": len(figs),
             "row_diff": sum(abs(f["ref_rows"] - f["cand_rows"]) for f in figs),
             "value_mae": (sum(f["value_mae"] * f["aligned_points"] for f in aligned)
                           / sum(f["aligned_points"] for f in aligned)) if aligned else None,
             "figures": figs}

    return {"reference": str(ref_path), "candidate": str(cand_path),
            "iou_threshold": threshold,
            "detection": detection, "presence": presence, "localization": localization,
            "reading_order": reading_order, "hierarchy": hierarchy,
            "rhetorical": rhetorical, "caption_linking": linking, "chart_data": chart}


def fmt(v):
    return "n/a" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reference", type=Path)
    ap.add_argument("candidate", type=Path)
    ap.add_argument("-o", "--output", type=Path, help="write full JSON report")
    ap.add_argument("--iou", type=float, default=0.5, help="IoU threshold for matching (default 0.5)")
    args = ap.parse_args()

    rep = evaluate(args.reference, args.candidate, args.iou)
    d, l, ro, h, rh, cl, cd = (rep[k] for k in
        ("detection", "localization", "reading_order", "hierarchy",
         "rhetorical", "caption_linking", "chart_data"))
    print(f"PAX evaluation — candidate vs reference (IoU ≥ {args.iou})")
    print(f"[1] detection        P={fmt(d['precision'])} R={fmt(d['recall'])} F1={fmt(d['f1'])} "
          f"({d['matched']}/{d['ref_elements']} ref, {d['cand_elements']} cand)")
    print(f"[2] localization     mean IoU={fmt(l['mean_iou'])} over {l['pairs']} matches")
    print(f"[3] reading order    Kendall τ={fmt(ro['kendall_tau'])} over {ro['pairs']} pairs")
    print(f"[4] hierarchy        tree edit distance={h['tree_edit_distance']} "
          f"(similarity={fmt(h['similarity'])}; {h['ref_sections']} vs {h['cand_sections']} sections)")
    print(f"[5] rhetorical       role={fmt(rh['role_accuracy'])} matter={fmt(rh['matter_accuracy'])} "
          f"level={fmt(rh['level_accuracy'])} over {rh['sections_compared']} sections")
    print(f"[6] caption linking  P={fmt(cl['precision'])} R={fmt(cl['recall'])} "
          f"({cl['ref_links']} ref links, {cl['cand_links']} cand)")
    print(f"[7] chart data       {cd['figures_compared']} figure(s); row diff={cd['row_diff']}; "
          f"value MAE={fmt(cd['value_mae'])}")
    if args.output:
        args.output.write_text(json.dumps(rep, indent=2))
        print(f"\nfull report → {args.output}")


if __name__ == "__main__":
    main()
