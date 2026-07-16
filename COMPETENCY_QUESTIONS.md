# PAX competency questions

*Starter set, v0.2.0 (2026-07-15) — drafted post-hoc against the shipped example
(`examples/Mercadier2011.jsonld`) and pending external review. Each question is
answerable with SPARQL over a conformant PAX graph; representative queries included.
Prefixes as in `context.jsonld`.*

## Structure

**CQ1 — What is the section hierarchy of the paper?**
```sparql
SELECT ?parent ?child ?title WHERE {
  ?parent po:contains ?child .
  ?child a doco:Section ; dcterms:title ?title .
}
```

**CQ2 — Which elements does a given section contain, in reading order?**
```sparql
SELECT ?el ?type ?pos WHERE {
  ?section dcterms:title "Results" ; po:contains+ ?el .
  ?el schema:position ?pos ; a ?type .
} ORDER BY ?pos
```

**CQ3 — Which figure belongs to which caption?** (the DoCO box pattern)
```sparql
SELECT ?fig ?cap WHERE {
  ?box a doco:FigureBox ; po:contains ?fig, ?cap .
  ?fig a doco:Figure . ?cap a deo:Caption .
}
```

**CQ4 — What is the rhetorical role of each section?** (double-typing)
```sparql
SELECT ?section ?role WHERE {
  ?section a doco:Section, ?role .
  FILTER(STRSTARTS(STR(?role), STR(deo:)))
}
```

**CQ5 — Which sections sit in front, body, or back matter?**
Via containment (`?matter po:contains ?section` with `?matter a doco:FrontMatter` …)
or the materialized `pax:matter` — the recommended SHACL profile guarantees the two agree.

## Pages and space

**CQ6 — Where on which page is a given element?**
```sparql
SELECT ?page ?xywh WHERE {
  ?el pax:onPage ?page ; pax:region/oa:hasSelector/rdf:value ?xywh .
}
```

**CQ7 — What is the printed page label of the N-th page of the PDF?**
```sparql
SELECT ?label WHERE {
  ?page a fabio:Page ; schema:position 3 ; pax:printedPageLabel ?label .
}
```
(The label — possibly non-numeric: "xiii", "S12" — is authoritative;
`pax:printedPageNumber` is the derived integer.)

**CQ8 — Which figures are chart-like, and what data was extracted from them?**
```sparql
SELECT ?fig ?type ?data WHERE {
  ?fig a doco:Figure ; pax:figureType ?type .
  OPTIONAL { ?fig pax:chartData ?data }
}
```
Chart-type membership is a SKOS question: `?type skos:inScheme pax:FigureTypeScheme`.

## Provenance and identity

**CQ9 — Which pipeline run and which model versions produced this graph?**
```sparql
SELECT ?activity ?agent ?version WHERE {
  ?ds a schema:Dataset ; prov:wasGeneratedBy ?activity .
  ?activity prov:wasAssociatedWith ?agent .
  ?agent schema:softwareVersion ?version .
}
```

**CQ10 — What license applies to the extracted graph (not the article)?**
`?ds a schema:Dataset ; dcterms:license ?lic ; schema:about ?paper .` —
the article node carries no license by design.

**CQ11 — What supplementary material does the paper have, and has it been processed?**
```sparql
SELECT ?si ?label WHERE {
  ?si frbr:supplementOf ?paper ; rdfs:label|dcterms:title ?label .
}
```
A layer-1 stub has no `po:contains`; a processed SI (layer 2) is a full recursive
document graph.

## Evaluation (the purpose)

**CQ12 — Do two graphs of the same paper (reference vs candidate pipeline) agree on…**
- element detection — the multiset of `(type, page)` pairs (CQ2 + CQ6);
- localization — matched elements' `xywh` selectors (CQ6; IoU computed by the engine);
- reading order — the `schema:position` sequences (CQ2);
- hierarchy — the `po:contains` section trees (CQ1);
- rhetorical labelling — `deo:*` / matter assignments (CQ4, CQ5);
- caption linking — box membership edges (CQ3);
- chart extraction — `pax:chartData` payloads (CQ8).

Every evaluation metric is thus grounded in a competency question the graph answers
directly; tolerances and scoring live in the evaluation engine, not in the vocabulary.
