# LinkML spike — findings and verdict

*Branch `linkml-spike`, 2026-07-16. Question: what does LinkML actually buy us on the
consumer/producer side, ahead of the paper-atomizer adapter? (The v0.2 decision stands:
`pax.ttl` remains hand-authored; this spike is about INSTANCE-data tooling only.)*

## Verdict, artifact by artifact (all measured, none projected)

| Artifact | Fidelity measured | Verdict |
|---|---|---|
| **Pydantic models** (`gen-pydantic`) | **78/78 nodes** of the real Mercadier graph parse through the generated models; validation is real (rejects a non-integer `position` and unknown fields — `extra="forbid"`) | **✅ Adopt for the adapter.** This is the artifact we lacked: typed, validating models to *build* graphs with. |
| **JSON-LD context** (`gen-jsonld-context`) | **38/38 shared terms** expand to the same IRIs as the hand-authored `context.jsonld`; 0 terms missing | **✅ Usable as drift guard** — a CI check comparing generated vs hand-authored context catches divergence. Not (yet) a replacement: swapping the published context is a breaking change governed by VERSIONING.md. |
| **JSON Schema** (`gen-json-schema`) | generated cleanly; not independently exercised | ◽ Nice-to-have for non-Python consumers; no current need. |
| **SHACL** (`gen-shacl`) | 28 shape constructs, **0** patterns / hasValue / SPARQL constraints / severity levels / targetSubjectsOf — vs the hand-authored profiles' 64 constructs with 26 such features; output also proved **non-deterministic across runs** (unordered `sh:ignoredProperties`) | **❌ Cannot own our shapes.** The severity contract, the projection-consistency SPARQL, the xywh pattern, and the ChartDataShape are inexpressible; not even committed (would break the drift gate). Hand-authored profiles stay. |

## What the spike surfaced (its real payoff)

1. **A live bug in the evaluation engine, fixed on master (`45b99c8`).** Real exports emit
   `pax:level` / `pax:matter` / `pax:pageStart` / `pax:pageEnd` / `pax:parsedContent` as
   *prefixed CURIE keys* — the shipped context deliberately defines no shortcuts for them.
   The rhetorical metric read only the shortcut form, so matter/level accuracy compared
   `None == None` on real data: vacuously 1.0. Caught red (0 real values compared),
   fixed with `pget()` + vacuousness-guard counts, verified green (9/9 sections).
2. **The JSON-LD ↔ Pydantic seam needs a shim** (documented in `test_roundtrip.py`):
   `@id`/`@type` are not valid Python field names (mapped to `id`/`category`); blank
   nodes (regions, selectors) have no `@id` while LinkML identifiers are required
   (synthesized); prefixed CURIE keys are normalized. An adapter built on these models
   needs this shim — or the exporter conventions change (a context/versioning decision).
3. **Prefix friction**: LinkML's built-in types pin `schema:` to `http://schema.org/`;
   our graphs use `https://` — resolved by using the `sdo:` prefix internally (emitted
   RDF identical).
4. **`rdf:JSON` has no LinkML equivalent either** — `chartData` is `linkml:Any`,
   mirroring the vocabulary's own decision to leave the OWL range unstated.

## Recommendation for the adapter (and v0.3)

- Build the **paper-atomizer adapter on the generated Pydantic models** (`generated/pax_instance.py`)
  plus a small serializer that inverts the shim (`id`→`@id`, `category`→`@type`, prefixed
  keys, drop synthetic blank-node ids). Producing through validating models is the point:
  a malformed graph fails at construction, not at SHACL time.
- Add a CI step (when this merges): regenerate the context from LinkML and diff the term
  expansions against `context.jsonld` — a mechanical drift guard on top of validate.py's
  bijection checks.
- Do **not** migrate vocabulary or shapes authoring. The measured SHACL gap is decisive,
  and the OWL side was never in scope.

## Regenerating

```bash
python3 scripts/build_linkml.py                          # pinned linkml==1.11.1, deterministic
uv run --with pydantic python linkml/test_roundtrip.py   # fidelity gates
```

The build pins LinkML 1.11.1 (gen-pydantic output is not stable across releases) and
strips the context generator's `generation_date` stamp; double-build verified
byte-deterministic, so CI regenerates and fails on any drift of `linkml/generated/`.
