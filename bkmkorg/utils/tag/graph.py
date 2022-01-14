#!/usr/bin/env python
"""
Tagset Reading

"""
import re
from dataclasses import dataclass, field
import logging as root_logger
from os import listdir
from os.path import (abspath, exists, expanduser, isdir, isfile, join, split,
                     splitext)
from typing import (Any, Callable, ClassVar, Dict, Generic, Iterable, Iterator,
                    List, Mapping, Match, MutableMapping, Optional, Sequence,
                    Set, Tuple, TypeVar, Union, cast)

import networkx as nx
import regex
from bkmkorg.io.reader.netscape import open_and_extract_bookmarks
from bkmkorg.io.reader.plain_bookmarks import load_plain_file
from bkmkorg.utils.tag.collection import TagFile
from bkmkorg.utils.bookmarks.collection import BookmarkCollection

logging = root_logger.getLogger(__name__)

IGNORE_REPLACEMENTS = ["TO_CHECK"]

TAG_NORM = regex.compile(" +")

Path = str
Tag  = str

@dataclass
class TagGraph:
    graph     : nx.Graph = field(default_factory=nx.Graph)

    org_pattern  : str        = r"^\*\*\s+.+?\s+:(\S+):$"
    org_sep      : str        = ":"
    norm_regex   : re.Pattern = TAG_NORM

    def extract_bibtex(self, db:'bibtexparser.BibtexDatabase') -> TagFile:
        logging.info("Processing Bibtex: {}".format(len(db.entries)))

        proportion = int(len(db.entries) / 10)
        count = 0
        total = TagFile()

        for i, entry in enumerate(db.entries):
            if i % proportion == 0:
                logging.info("{}/10 Complete".format(count))
                count += 1

            #get tags
            total.update(self.link(entry['tags']))

        return total

    def extract_org(self, org_files:List[Path], tag_regex=None) -> TagFile:
        logging.info("Extracting data from orgs")
        if tag_regex is None:
            tag_regex = self.org_pattern

        ORG_TAG_REGEX = regex.compile(tag_regex)
        total = TagFile()

        for org in org_files:
            #read
            text = []
            with open(org,'r') as f:
                text = f.readlines()

            #line by line
            for line in text:
                tags = ORG_TAG_REGEX.findall(line)
                e_tags = []
                if not bool(tags):
                    continue

                e_tags = [x for x in tags[0].split(self.org_sep)]
                total.update(self.link(e_tags))

        return total

    def extract_bookmark(self, bkmk_files: List[Path]) -> TagFile:
        total = TagFile()
        for bkmk_f in bkmk_files:
            bkmks = BookmarkCollection.read(bkmk_f)

            for bkmk in bkmks:
                tags          = bkmk.tags
                total.update(self.link(tags))

        return total

    def link(self, tags:Iterable[Tag]) -> Iterable[Tag]:
        """
        Add a set of tags to the graph, after normalising
        """
        norm_tags = [self.norm_regex.sub("_", x.strip()) for x in tags if bool(x)]
        remaining = norm_tags[:]

        [self.graph.add_node(x, count=0) for x in norm_tags if x not in self.graph]

        for tag in norm_tags:
            self.graph.nodes[tag]['count'] += 1
            remaining.remove(tag)
            edges_to_increment = [(tag, y) for y in remaining]
            for u,v in edges_to_increment:
                if not self.graph.has_edge(u,v):
                    self.graph.add_edge(u,v, weight=0)

                self.graph[u][v]['weight'] += 1

        return norm_tags



    def write(self, target):
        nx.write_weighted_edgelist(self.graph, abspath(expanduser(target)))

    def __str__(self):
        keys    = self.tags
        tag_str = "\n".join(["{} : {}".format(k, self.graph.nodes[k]['count']) for k in keys])
        return tag_str


    @property
    def tags(self) -> TagFile:
        result = TagFile()
        for tag in self.graph.nodes:
            result.set(tag, self.graph.nodes[tag]['count'])
        return result

    def get_count(self, tag:Tag):
        if tag not in self.graph:
            return 0
        return self.graph[tag]['count']

#  ############################################################################
def read_substitutions(target: Union[str, List[str]], counts=True) -> Dict[str, List[str]]:
    """ Read a text file of the form (with counts):
    tag : num : sub : sub : sub....
    without counts:
    tag : sub : sub : ...
    returning a dict of {tag : [sub]}
    """
    raise DeprecationWarning("use bkmkorg.utils.tag.collection.TagFile")