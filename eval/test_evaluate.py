#!/usr/bin/env python3
"""Perturbation tests for the PAX evaluation engine.

Discipline: every metric must be OBSERVED failing for the right reason before
its pass means anything. Each test perturbs the real Mercadier 2011 graph in
exactly one way, then asserts (a) the targeted metric degrades in the expected
direction, and (b) the metrics that should be blind to that perturbation stay
perfect. The identity comparison (reference vs itself) must be perfect on all
seven metrics.

Run:  python3 eval/test_evaluate.py
"""

import copy
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from evaluate import evaluate, zss_distance  # noqa: E402

HERE = Path(__file__).parent
REF = HERE.parent / "examples" / "Mercadier2011.jsonld"
E = "https://w3id.org/alexandria/paper/mercadier2011/run/e88f86e"

failures = []


def check(ok, msg):
    print(("  ✓ " if ok else "  ✗ ") + msg)
    if not ok:
        failures.append(msg)


def perturbed(mutate):
    """Apply `mutate(kg_dict, nodes_by_id)` to a deep copy; return temp path."""
    kg = json.loads(REF.read_text())
    kg = copy.deepcopy(kg)
    nodes = {n["@id"]: n for n in kg["@graph"]}
    mutate(kg, nodes)
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonld", delete=False)
    json.dump(kg, f)
    f.close()
    return Path(f.name)


def run(mutate=None):
    return evaluate(REF, perturbed(mutate) if mutate else REF)


# ---------------------------------------------------------------- ZSS sanity

def test_zss_known_cases():
    print("[0] Zhang–Shasha unit checks")
    a = ("f", [("d", [("a", []), ("c", [("b", [])])]), ("e", [])])
    b = ("f", [("c", [("d", [("a", []), ("b", [])])]), ("e", [])])
    check(zss_distance(a, a) == 0, "identical trees → 0")
    check(zss_distance(a, b) == 2, f"classic Zhang–Shasha example → 2 (got {zss_distance(a, b)})")
    leaf_del = ("f", [("d", [("a", [])]), ("e", [])])
    check(zss_distance(("f", [("d", [("a", []), ("z", [])]), ("e", [])]), leaf_del) == 1,
          "single leaf deletion → 1")
    check(zss_distance(("x", []), ("y", [])) == 1, "single rename → 1")


# ---------------------------------------------------------------- identity

def test_identity():
    print("[1] identity: reference vs itself must be perfect everywhere")
    r = run()
    check(r["detection"]["precision"] == 1 and r["detection"]["recall"] == 1, "detection P=R=1")
    check(r["localization"]["mean_iou"] == 1, "mean IoU = 1")
    check(r["reading_order"]["kendall_tau"] == 1, "Kendall τ = 1")
    check(r["hierarchy"]["tree_edit_distance"] == 0, "tree edit distance = 0")
    check(r["rhetorical"]["role_accuracy"] == 1 and r["rhetorical"]["matter_accuracy"] == 1
          and r["rhetorical"]["level_accuracy"] == 1, "rhetorical accuracies = 1")
    check(r["caption_linking"]["precision"] == 1 and r["caption_linking"]["recall"] == 1,
          "caption links P=R=1")
    check(r["chart_data"]["row_diff"] == 0 and r["chart_data"]["value_mae"] == 0,
          "chart data identical (row diff 0, MAE 0)")


# ---------------------------------------------------------------- detection

def test_missing_element():
    print("[2] deleted paragraph → recall drops, precision stays 1")
    victim = f"{E}/element/9"
    def m(kg, nodes):
        kg["@graph"] = [n for n in kg["@graph"] if n["@id"] != victim]
        for n in kg["@graph"]:
            if victim in n.get("contains", []):
                n["contains"].remove(victim)
    r = run(m)
    check(r["detection"]["recall"] < 1, f"recall {r['detection']['recall']:.3f} < 1")
    check(r["detection"]["precision"] == 1, "precision stays 1")
    check(r["localization"]["mean_iou"] == 1, "IoU of surviving matches stays 1")


def test_spurious_element():
    print("[3] hallucinated paragraph → precision drops, recall stays 1")
    def m(kg, nodes):
        ghost = copy.deepcopy(nodes[f"{E}/element/9"])
        ghost["@id"] = f"{E}/element/999"
        ghost["position"] = 999
        ghost["region"][0]["hasSelector"]["value"] = "xywh=10,10,50,50"
        kg["@graph"].append(ghost)
        nodes[f"{E}/section/3"]["contains"].append(ghost["@id"])
    r = run(m)
    check(r["detection"]["precision"] < 1, f"precision {r['detection']['precision']:.3f} < 1")
    check(r["detection"]["recall"] == 1, "recall stays 1")


# ---------------------------------------------------------------- localization

def test_small_bbox_shift():
    print("[4] 30px bbox shift → IoU drops, detection unaffected")
    def m(kg, nodes):
        sel = nodes[f"{E}/element/9"]["region"][0]["hasSelector"]
        x, y, w, h = map(int, sel["value"][5:].split(","))
        sel["value"] = f"xywh={x + 30},{y},{w},{h}"
    r = run(m)
    check(r["detection"]["recall"] == 1, "still matched (detection R=1)")
    check(r["localization"]["mean_iou"] < 1, f"mean IoU {r['localization']['mean_iou']:.3f} < 1")
    check(r["reading_order"]["kendall_tau"] == 1, "reading order blind to the shift")


def test_large_bbox_shift():
    print("[5] bbox moved across the page → match lost below IoU threshold")
    def m(kg, nodes):
        sel = nodes[f"{E}/element/9"]["region"][0]["hasSelector"]
        sel["value"] = "xywh=900,100,306,498"
    r = run(m)
    check(r["detection"]["recall"] < 1, f"recall {r['detection']['recall']:.3f} < 1")
    check(r["detection"]["precision"] < 1, "the displaced candidate counts against precision")


# ---------------------------------------------------------------- reading order

def test_swapped_reading_order():
    print("[6] two positions swapped → Kendall τ drops, nothing else moves")
    def m(kg, nodes):
        a, b = nodes[f"{E}/element/9"], nodes[f"{E}/element/10"]
        a["position"], b["position"] = b["position"], a["position"]
    r = run(m)
    check(r["reading_order"]["kendall_tau"] < 1,
          f"τ {r['reading_order']['kendall_tau']:.3f} < 1")
    check(r["detection"]["recall"] == 1 and r["localization"]["mean_iou"] == 1,
          "detection and IoU unaffected")


# ---------------------------------------------------------------- rhetorical

def test_dropped_rhetorical_type():
    print("[7] deo:Introduction removed → role accuracy drops")
    def m(kg, nodes):
        n = nodes[f"{E}/section/3"]
        n["@type"] = [t for t in n["@type"] if t != "deo:Introduction"]
    r = run(m)
    check(r["rhetorical"]["role_accuracy"] < 1,
          f"role accuracy {r['rhetorical']['role_accuracy']:.3f} < 1")
    check(r["rhetorical"]["matter_accuracy"] == 1 and r["rhetorical"]["level_accuracy"] == 1,
          "matter/level accuracies unaffected")


def test_wrong_matter():
    print("[8] section matter flipped → matter accuracy drops")
    def m(kg, nodes):
        nodes[f"{E}/section/8"]["matter"] = "back"
    r = run(m)
    check(r["rhetorical"]["matter_accuracy"] < 1,
          f"matter accuracy {r['rhetorical']['matter_accuracy']:.3f} < 1")
    check(r["rhetorical"]["role_accuracy"] == 1, "role accuracy unaffected")


# ---------------------------------------------------------------- hierarchy

def test_flattened_subsection():
    print("[9] subsection hoisted to top level → tree distance grows")
    sub = f"{E}/section/6"
    def m(kg, nodes):
        nodes[f"{E}/section/5"]["contains"].remove(sub)
        nodes[f"{E}/body-matter"]["contains"].append(sub)
    r = run(m)
    check(r["hierarchy"]["tree_edit_distance"] > 0,
          f"tree edit distance {r['hierarchy']['tree_edit_distance']} > 0")
    check(r["hierarchy"]["similarity"] < 1, "similarity < 1")
    check(r["detection"]["recall"] == 1, "element detection blind to the re-parenting")


# ---------------------------------------------------------------- caption links

def test_swapped_captions():
    print("[10] captions swapped between two figure boxes → link P/R drop")
    def m(kg, nodes):
        b1, b2 = nodes[f"{E}/box/19"], nodes[f"{E}/box/21"]
        c1, c2 = f"{E}/element/20", f"{E}/element/22"
        for key in ("contains", "hasPart"):
            if key in b1:
                b1[key] = [c2 if x == c1 else x for x in b1[key]]
                b2[key] = [c1 if x == c2 else x for x in b2[key]]
    r = run(m)
    check(r["caption_linking"]["recall"] < 1,
          f"link recall {r['caption_linking']['recall']:.3f} < 1")
    check(r["caption_linking"]["precision"] < 1, "link precision < 1")
    check(r["detection"]["recall"] == 1, "element detection unaffected")


# ---------------------------------------------------------------- chart data

def test_chart_value_error():
    print("[11] chart y-values scaled ×1.1 → value MAE > 0, rows unchanged")
    def m(kg, nodes):
        cd = nodes[f"{E}/element/24"]["chartData"]
        charts = cd if isinstance(cd, list) else [cd]
        for c in charts:
            for row in c.get("data", []):
                if isinstance(row.get("y"), list):
                    row["y"] = [v * 1.1 if isinstance(v, (int, float)) else v for v in row["y"]]
                elif isinstance(row.get("y"), (int, float)):
                    row["y"] = row["y"] * 1.1
    r = run(m)
    check(r["chart_data"]["value_mae"] and r["chart_data"]["value_mae"] > 0,
          f"value MAE {r['chart_data']['value_mae']:.3f} > 0")
    check(r["chart_data"]["row_diff"] == 0, "row counts unchanged")


def test_chart_missing_rows():
    print("[12] 5 chart rows dropped → row diff = 5")
    def m(kg, nodes):
        cd = nodes[f"{E}/element/24"]["chartData"]
        charts = cd if isinstance(cd, list) else [cd]
        removed = 0
        for c in charts:
            while removed < 5 and c.get("data"):
                c["data"].pop()
                removed += 1
    r = run(m)
    check(r["chart_data"]["row_diff"] == 5,
          f"row diff {r['chart_data']['row_diff']} == 5")


def main():
    for fn in (test_zss_known_cases, test_identity, test_missing_element,
               test_spurious_element, test_small_bbox_shift, test_large_bbox_shift,
               test_swapped_reading_order, test_dropped_rhetorical_type,
               test_wrong_matter, test_flattened_subsection, test_swapped_captions,
               test_chart_value_error, test_chart_missing_rows):
        fn()
    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        sys.exit(1)
    print("ALL EVALUATION-ENGINE TESTS PASSED")


if __name__ == "__main__":
    main()
