# OOPS! scan — PAX v0.2.0 — findings and dispositions

- **Date**: 2026-07-15
- **Tool**: OOPS! web service, `https://oops.linkeddata.es/rest` (REST API; no version
  string exposed by the service — raw response archived as [`oops-report.rdf`](oops-report.rdf))
- **Input**: `docs/vocab/ontology.owl` (RDF/XML serialization of pax.ttl v0.2.0, standalone document)
- **Result**: 6 pitfalls (2 Important, 4 Minor), 0 Critical. Dispositions below; **no change
  to the vocabulary required for v0.2.0**, one candidate queued for v0.3.

| # | Pitfall | Importance | Disposition |
|---|---|---|---|
| P10 | Missing disjointness (1) | Important | **Deferred to v0.3 (candidate)** |
| P11 | Missing domain or range (14) | Important | **Rejected — deliberate, review-mandated** |
| P04 | Unconnected ontology elements (9) | Minor | **Rejected — by design + false positives** |
| P08 | Missing annotations (11) | Minor | **Rejected — false positives (external terms)** |
| P13 | Inverse relationships not declared (5) | Minor | **Rejected — by design** |
| P21 | Miscellaneous class `pax:OtherElement` (1) | Minor | **Rejected — documented design** |

## Rationale

**P11 — Missing domain/range.** The absent domains are a *review-mandated fix*, not an
omission: v0.1 declared `rdfs:domain doco:Section` on `pax:level/matter/pageStart/pageEnd`,
which entailed that `doco:Label` headings are sections (a real inference bug caught in
external review pass 1). The domains were deliberately dropped; enforcement lives in the
SHACL core profile, which OOPS does not read. `pax:chartData` has no range because
`rdf:JSON` is outside the OWL 2 datatype map (a range axiom would break the DL profile);
the datatype is enforced by `paxs:ChartDataShape`. `skos:inScheme` in the list is an
external term. This pitfall is the OWL-heavy worldview PAX explicitly does not follow —
the vocabulary's logical force is in its SHACL gates, not deep OWL axioms.

**P10 — Missing disjointness.** The five PAX element classes (`PageHeader`, `PageFooter`,
`PageNumberMark`, `CodeBlock`, `OtherElement`) carry no mutual `owl:disjointWith`. Adding
them would be harmless (backward-compatible, MINOR per [VERSIONING.md](../../../../VERSIONING.md))
and is queued as a **v0.3 candidate**, pending re-run of the formal checks and reviewer
acknowledgement. Not changed in v0.2.0: the release is frozen post-review.

**P04 — Unconnected elements.** The PAX element classes are instantiated and connected at
the *instance* level (`po:contains`, `pax:onPage`, `pax:region`); the vocabulary profile
deliberately adds no axiomatic scaffolding around them. `foaf:Organization`/`foaf:Person`
in the list are local OWL-category compatibility declarations for external terms (needed
by OWLAPI tooling), not PAX elements.

**P08 — Missing annotations.** Every listed element is an *external* term
(`skos:Concept`, `oa:ResourceSelection`, `fabio:Page`, `foaf:*`, `voaf:Vocabulary`,
`schema:parentOrganization`) — annotated in its home vocabulary; PAX only carries category
declarations for them. All PAX-namespace terms have `rdfs:label` + `rdfs:comment`
(ROBOT lint: 0 errors, see [`lint-report.tsv`](lint-report.tsv)).

**P13 — Inverses.** Deliberate: consumers traverse with SPARQL property paths; reused
properties keep whatever inverses their home ontologies define (e.g. PO defines
`po:isContainedBy`). Declaring PAX-side inverses would add reasoning surface without a
consumer.

**P21 — Miscellaneous class.** `pax:OtherElement` is the honest OCR passthrough — it
preserves the raw type string via `pax:rawType` precisely so that unclassifiable elements
remain visible to the evaluation layer instead of being silently dropped. Documented in
the term's comment; keeping it is a design commitment.
