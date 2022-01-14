"""
Provide Utility classes for working with bookmarks
"""
import logging as root_logger
from dataclasses import InitVar, dataclass, field
from typing import (Any, Callable, ClassVar, Dict, Generic, Iterable, Iterator,
                    List, Mapping, Match, MutableMapping, Optional, Sequence,
                    Set, Tuple, TypeVar, Union, cast)
import urllib.parse as url_parse

import regex
from bs4 import BeautifulSoup

logging = root_logger.getLogger(__name__)

TAG_NORM = regex.compile(" +")
file     = Any

@dataclass
class Bookmark:
    url     : str      = field()
    tags    : Set[str] = field(default_factory=set)
    name    : str      = field(default="No Name")
    tag_sep : str      = field(default=":")
    url_sep : str      = field(default=" : ")

    def __post_init__(self):
        self.tags = [TAG_NORM.sub("_", x.strip()) for x in self.tags]

    def __eq__(self, other):
        return self.url == other.url

    def __lt__(self, other):
        return self.url < other.url

    def __str__(self):
        tags = self.url_sep.join(sorted(self.tags))
        return f"{self.url}{self.url_sep}{tags}"

    @staticmethod
    def build(line, url_sep=None, tag_sep=None):
        assert(isinstance(line, str))
        if url_sep is None:
            url_sep = Bookmark.url_sep
        if tag_sep is None:
            tag_sep = Bookmark.tag_sep

        line_split = line.split(" :")
        url        = line_split[0]
        tags       = line_split[1:]
        tag_set    = {x.strip() for x in tags}
        if not bool(tag_set):
            logging.warning(f"No Tags for: {url}")

        return Bookmark(url,
                        tag_set,
                        tag_sep=tag_sep,
                        url_sep=url_sep)


    @property
    def url_comps(self) -> url_parse.ParseResult:
        return url_parse.urlparse(self.url)

    def merge(self, other) -> 'Bookmark':
        assert(self == other)
        merged = Bookmark(self.url,
                          self.tags.union(other.tags),
                          self.name,
                          self.tag_sep,
                          self.url_sep)
        return merged

    def clean(self, subs):
        cleaned_tags = set()
        for tag in self.tags:
            cleaned_tags.add(sub.get_sub(tag))

        self.tags = cleaned_tags

@dataclass
class BookmarkCollection:
    entries : List[Bookmark] = field(default_factory=list)
    ext     : str            = field(default=".bookmarks")

    @staticmethod
    def read(f:file) -> "BookmarkCollection":
        bookmarks = BookmarkCollection()
        for line in f.readlines():
            bookmarks += Bookmark.build(line)

        return bookmarks

    @staticmethod
    def read_netscape(path:str):
        logging.info('Starting html opener for: {}'.format(path))
        with open(path, 'rb') as f:
            rawHtml = f.read().decode("utf-8","ignore")

        soup     = BeautifulSoup(rawHtml,'html.parser')
        bkmkList = __getLinks(soup)
        logging.info("Found {} links".format(len(bkmkList)))
        return BookmarkCollection(bkmkList)
    
    def add_file(self, f:file):
        for line in f.readlines():
            self += Bookmark.build(line)

    def __str__(self):
        return "\n".join([str(x) for x in sorted(self.entries)])

    def __iadd__(self, value):
        assert(isinstance(value, (BookmarkCollection, Bookmark, list)))
        if isinstance(value, Bookmark):
            self.entries.append(value)
        elif isinstance(value, BookmarkCollection):
            self.entries += value.entries
        elif isinstance(value, list):
            assert(all([isinstance(x, Bookmark) for x in value]))
            self.entries += value
        else:
            raise TypeError(type(value))


    def __iter__(self):
        return iter(self.entries)

    def __contains__(self, value:Bookmark):
        return value in self.entries

    def difference(self, other:BookmarkCollection):
        result = BookmarkCollection()
        for bkmk in other:
            if bkmk not in self:
                result += bkmk

        return result

    def merge_duplicates(self):
        deduplicated = {}
        for x in self:
            if x.url not in deduplicated:
                deduplicated[x.url] = x
            else:
                deduplicated[x.url] = x.merge(deduplicated[x.url])

        self.entries = list(deduplicated.values())

######################################################################
def __getLinks(aSoup) -> List[Bookmark]:
    bkmks = aSoup.find_all('a')
    bkmkList = []
    for x in bkmks:
        tagString = x.get('tags')
        if tagString is not None:
            indTags = tagString.split(',')
        else:
            indTags = []
        tagSet = set(indTags)
        newBkmk = Bookmark(x.get('href'),tagSet, name=x.get_text())
        bkmkList.append(newBkmk)

    return bkmkList