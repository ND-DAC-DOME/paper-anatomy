# PAX versioning and compatibility policy

*Status: adopted with testing v0.2.0 (2026-07-15). Governs every change from here on.*

## Identifiers

- **Term IRIs are stable and unversioned**: `https://w3id.org/paper-anatomy/vocab#<Term>`.
  A term IRI, once released, is never deleted, never reassigned to a different meaning.
- **Releases are snapshotted**, not rewritten: `releases/<MAJOR.MINOR.PATCH>/vocab.ttl`
  (+ `shapes/`), referenced from the ontology header via `owl:versionIRI
  <https://w3id.org/paper-anatomy/releases/<version>/vocab>`. `owl:priorVersion` links
  each release to the previous *retrievable* one.
- The **JSON-LD context** (`context.jsonld`) is a published contract with the same
  compatibility rules as the vocabulary: term shortcuts may be added in MINOR releases;
  changed or removed only in MAJOR releases.

## What each version part means

| Part | Bumped when | Consumer impact |
|---|---|---|
| **PATCH** | editorial fixes: labels, comments, documentation, metadata; no change to any axiom, term set, shape constraint, or context term | none — safe to update blindly |
| **MINOR** | backward-compatible additions: new terms, new SKOS concepts, new optional shape checks (Warning/Info), relaxed constraints | existing data remains conformant |
| **MAJOR** | anything that can invalidate existing conformant data: removing/renaming context terms, strengthening core (Violation) constraints, changing a term's semantics, deprecations taking effect | migration notes required in the changelog |

The **core SHACL profile is part of the compatibility surface**: a change that makes
previously-conformant data fail core validation is MAJOR, even if no OWL axiom changed.

## Deprecation

1. Mark the term `owl:deprecated true`, keep all annotations, add an `rdfs:comment`
   naming the replacement (and `dcterms:isReplacedBy` when one exists). This is a MINOR
   change.
2. Deprecated terms keep resolving and keep their definitions for at least one MAJOR
   cycle; validation treats their use as a Warning, never a core Violation, during that
   window.
3. Removal from the context (the only true removal — the IRI itself is never reused)
   happens at the next MAJOR release.

Precedent inside v0.x: `pax:sequenceNumber` was **removed outright** rather than
deprecated — allowed only because nothing was published; from v0.2.0 on, the procedure
above applies.

## Pre-1.0 caveat

While the vocabulary is in testing (0.x), MINOR releases may carry breaking changes
**if and only if** they are demanded by external design review; each such change must be
listed explicitly in the release notes. From 1.0.0 the table above binds unconditionally.

## Release procedure

1. All CI layers green (`validate.py`, `formal_checks.py`).
2. Copy `pax.ttl` → `releases/<version>/vocab.ttl`, `shapes/*.ttl` → `releases/<version>/shapes/`;
   update `owl:versionInfo`, `owl:versionIRI`, `owl:priorVersion`, `dcterms:modified`.
3. Regenerate `docs/` (`python3 scripts/build_docs.py --quality`) so the published spec,
   serializations, and quality evidence match the release.
4. Tag the repository `v<version>`.
