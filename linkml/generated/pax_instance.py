from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.11.0"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'paxi',
     'default_range': 'string',
     'description': 'Instance-data model for Paper Anatomy (PAX) knowledge graphs: '
                    'the node kinds and slots of the compacted JSON-LD produced by '
                    'exporters and consumed by the evaluation engine.',
     'id': 'https://w3id.org/paper-anatomy/linkml/pax-instance',
     'imports': ['linkml:types'],
     'license': 'https://creativecommons.org/licenses/by/4.0/',
     'name': 'pax-instance',
     'prefixes': {'dcterms': {'prefix_prefix': 'dcterms',
                              'prefix_reference': 'http://purl.org/dc/terms/'},
                  'deo': {'prefix_prefix': 'deo',
                          'prefix_reference': 'http://purl.org/spar/deo/'},
                  'doco': {'prefix_prefix': 'doco',
                           'prefix_reference': 'http://purl.org/spar/doco/'},
                  'fabio': {'prefix_prefix': 'fabio',
                            'prefix_reference': 'http://purl.org/spar/fabio/'},
                  'frbr': {'prefix_prefix': 'frbr',
                           'prefix_reference': 'http://purl.org/vocab/frbr/core#'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'oa': {'prefix_prefix': 'oa',
                         'prefix_reference': 'http://www.w3.org/ns/oa#'},
                  'pax': {'prefix_prefix': 'pax',
                          'prefix_reference': 'https://w3id.org/paper-anatomy/vocab#'},
                  'paxi': {'prefix_prefix': 'paxi',
                           'prefix_reference': 'https://w3id.org/paper-anatomy/linkml/pax-instance/'},
                  'po': {'prefix_prefix': 'po',
                         'prefix_reference': 'http://www.essepuntato.it/2008/12/pattern#'},
                  'prov': {'prefix_prefix': 'prov',
                           'prefix_reference': 'http://www.w3.org/ns/prov#'},
                  'rdf': {'prefix_prefix': 'rdf',
                          'prefix_reference': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'},
                  'sdo': {'prefix_prefix': 'sdo',
                          'prefix_reference': 'https://schema.org/'}},
     'source_file': '/mnt/slow_data/TAI/Users/pmoreira/paper-anatomy/linkml/pax-instance.yaml',
     'types': {'Any': {'base': 'Any',
                       'description': 'arbitrary JSON payload',
                       'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance',
                       'name': 'Any',
                       'uri': 'linkml:Any'}}} )


class NodeBase(ConfiguredBaseModel):
    """
    Common identity of every node in the graph.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True,
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class PaperExpression(NodeBase):
    """
    The article Expression (FRBR) — the graph's document root.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'fabio:JournalArticle',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    title: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Section', 'Supplement'],
         'slot_uri': 'dcterms:title'} })
    identifier: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Supplement'],
         'slot_uri': 'dcterms:identifier'} })
    pageCount: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression'], 'slot_uri': 'fabio:hasPageCount'} })
    embodiment: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression'], 'slot_uri': 'frbr:embodiment'} })
    contains: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Matter', 'Section', 'Box', 'Supplement'],
         'slot_uri': 'po:contains'} })
    supplement: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression'], 'slot_uri': 'frbr:supplement'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Manifestation(NodeBase):
    """
    The PDF manifestation; its parts are the pages.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'fabio:DigitalManifestation',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Manifestation', 'Dataset', 'Activity', 'SoftwareAgent'],
         'slot_uri': 'sdo:name'} })
    embodimentOf: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Manifestation'], 'slot_uri': 'frbr:embodimentOf'} })
    part: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Manifestation'], 'slot_uri': 'frbr:part'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Page(NodeBase):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'fabio:Page',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    position: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Page', 'DocumentElement'], 'slot_uri': 'sdo:position'} })
    image: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Page'], 'slot_uri': 'sdo:image'} })
    printedPageLabel: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Page'], 'slot_uri': 'pax:printedPageLabel'} })
    printedPageNumber: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Page'], 'slot_uri': 'pax:printedPageNumber'} })
    printedPagePosition: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Page'], 'slot_uri': 'pax:printedPagePosition'} })
    pageImageWidth: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Page'], 'slot_uri': 'pax:pageImageWidth'} })
    pageImageHeight: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Page'], 'slot_uri': 'pax:pageImageHeight'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Matter(NodeBase):
    """
    Front/body/back matter container (the concrete doco type lives in `category`).
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    contains: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Matter', 'Section', 'Box', 'Supplement'],
         'slot_uri': 'po:contains'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Section(NodeBase):
    """
    A section or subsection; DEO discourse roles ride in `category`.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'doco:Section',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    title: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Section', 'Supplement'],
         'slot_uri': 'dcterms:title'} })
    level: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Section'], 'slot_uri': 'pax:level'} })
    matter: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Section'], 'slot_uri': 'pax:matter'} })
    pageStart: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Section'], 'slot_uri': 'pax:pageStart'} })
    pageEnd: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Section'], 'slot_uri': 'pax:pageEnd'} })
    contains: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Matter', 'Section', 'Box', 'Supplement'],
         'slot_uri': 'po:contains'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class DocumentElement(NodeBase):
    """
    Leaf element on a page (paragraph, figure, table, caption, formula, …); the concrete doco/deo/pax type lives in `category`.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    position: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Page', 'DocumentElement'], 'slot_uri': 'sdo:position'} })
    onPage: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement'], 'slot_uri': 'pax:onPage'} })
    region: Optional[list[Region]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement'], 'slot_uri': 'pax:region'} })
    text: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement'], 'slot_uri': 'sdo:text'} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement', 'SoftwareAgent', 'Supplement'],
         'slot_uri': 'dcterms:description'} })
    figureType: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement'], 'slot_uri': 'pax:figureType'} })
    chartData: Optional[Any] = Field(default=None, description="""Extracted chart payload — rdf:JSON literal in the graph. LinkML (like OWL 2) has no rdf:JSON datatype; modeled as Any, mirroring the vocabulary's own decision to leave the range unstated.""", json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement'], 'slot_uri': 'pax:chartData'} })
    parsedContent: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement'], 'slot_uri': 'pax:parsedContent'} })
    rawType: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement'], 'slot_uri': 'pax:rawType'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Box(NodeBase):
    """
    Figure/Table box grouping the body element and its caption.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'doco:FigureBox',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    contains: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Matter', 'Section', 'Box', 'Supplement'],
         'slot_uri': 'po:contains'} })
    hasPart: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Box'], 'slot_uri': 'dcterms:hasPart'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Region(NodeBase):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'oa:ResourceSelection',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    hasSource: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Region'], 'slot_uri': 'oa:hasSource'} })
    hasSelector: Optional[FragmentSelector] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Region'], 'slot_uri': 'oa:hasSelector'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class FragmentSelector(NodeBase):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'oa:FragmentSelector',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    value: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['FragmentSelector'], 'slot_uri': 'rdf:value'} })
    conformsTo: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['FragmentSelector'], 'slot_uri': 'dcterms:conformsTo'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Dataset(NodeBase):
    """
    The extracted-graph node — carries provenance and the KG license.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'sdo:Dataset',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Manifestation', 'Dataset', 'Activity', 'SoftwareAgent'],
         'slot_uri': 'sdo:name'} })
    license: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset'], 'slot_uri': 'dcterms:license'} })
    about: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset'], 'slot_uri': 'sdo:about'} })
    wasDerivedFrom: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset'], 'slot_uri': 'prov:wasDerivedFrom'} })
    wasGeneratedBy: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset'], 'slot_uri': 'prov:wasGeneratedBy'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Activity(NodeBase):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'prov:Activity',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Manifestation', 'Dataset', 'Activity', 'SoftwareAgent'],
         'slot_uri': 'sdo:name'} })
    used: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Activity'], 'slot_uri': 'prov:used'} })
    wasAssociatedWith: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Activity'], 'slot_uri': 'prov:wasAssociatedWith'} })
    softwareVersion: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Activity', 'SoftwareAgent'], 'slot_uri': 'sdo:softwareVersion'} })
    startedAtTime: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Activity'], 'slot_uri': 'prov:startedAtTime'} })
    source: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Activity'], 'slot_uri': 'dcterms:source'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class SoftwareAgent(NodeBase):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'prov:SoftwareAgent',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Manifestation', 'Dataset', 'Activity', 'SoftwareAgent'],
         'slot_uri': 'sdo:name'} })
    softwareVersion: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Activity', 'SoftwareAgent'], 'slot_uri': 'sdo:softwareVersion'} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement', 'SoftwareAgent', 'Supplement'],
         'slot_uri': 'dcterms:description'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


class Supplement(NodeBase):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'fabio:SupplementaryInformationFile',
         'from_schema': 'https://w3id.org/paper-anatomy/linkml/pax-instance'})

    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Supplement'], 'slot_uri': 'sdo:name'} })
    title: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Section', 'Supplement'],
         'slot_uri': 'dcterms:title'} })
    identifier: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Supplement'],
         'slot_uri': 'dcterms:identifier'} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['DocumentElement', 'SoftwareAgent', 'Supplement'],
         'slot_uri': 'dcterms:description'} })
    contains: Optional[list[str]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PaperExpression', 'Matter', 'Section', 'Box', 'Supplement'],
         'slot_uri': 'po:contains'} })
    supplementOf: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Supplement'], 'slot_uri': 'frbr:supplementOf'} })
    id: str = Field(default=..., description="""Node IRI (JSON-LD `@id`).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })
    category: Optional[list[str]] = Field(default=None, description="""RDF types of the node (JSON-LD `@type`, compacted CURIEs).""", json_schema_extra = { "linkml_meta": {'domain_of': ['NodeBase']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
NodeBase.model_rebuild()
PaperExpression.model_rebuild()
Manifestation.model_rebuild()
Page.model_rebuild()
Matter.model_rebuild()
Section.model_rebuild()
DocumentElement.model_rebuild()
Box.model_rebuild()
Region.model_rebuild()
FragmentSelector.model_rebuild()
Dataset.model_rebuild()
Activity.model_rebuild()
SoftwareAgent.model_rebuild()
Supplement.model_rebuild()
