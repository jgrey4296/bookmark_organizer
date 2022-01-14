#!/usr/bin/env python3
"""
Utility class for working with tag files
"""
import logging as root_logger
import re
from collections import defaultdict
from dataclasses import InitVar, dataclass, field
from os import listdir
from os.path import (abspath, exists, expanduser, isdir, isfile, join, split,
                     splitext)
from typing import (Any, Callable, ClassVar, Dict, Generic, Iterable, Iterator,
                    List, Mapping, Match, MutableMapping, Optional, Sequence,
                    Set, Tuple, TypeVar, Union, cast)

from bkmkorg.utils.dfs.files import get_data_files

logging = root_logger.getLogger(__name__)

TAG_NORM = re.compile(" +")
file     = Any

@dataclass
class TagFile:
    """ A Basic TagFile holds the counts for each tag use """

    count   : Dict[str, int] = field(default_factory=lambda: defaultdict(lambda: 0))
    sep     : str            = field(default=":")
    ext     : str            = field(default=".tags")

    norm_regex : re.Pattern  = TAG_NORM

    @classmethod
    def builder(cls, target):
        """
        Build an tag file from a target directory or file
        """
        main = cls()
        for t in get_data_files(target, main.ext):
            try:
                with open(t, 'r') as f:
                    main += cls.read(f)
            except Exception as err:
                logging.warning(f"{cls.__name__} creation failure with {t}")

        return main

    @staticmethod
    def read(f:file) -> 'TagFile':
        obj = TagFile()
        for line in f.readlines():
            line_s = [obj.norm_regex.sub("_", x.strip()) for x in line.split(obj.sep)]
            obj.set_count(line_s[0], int(line_s[1]))

        return obj


    @staticmethod
    def read_bib(f:file) -> 'TagFile':
        raise NotImplementedError()
    @staticmethod
    def read_org(f:file) -> 'TagFile':
        raise NotImplementedError()

    @staticmethod
    def read_html(f:file) -> 'TagFile':
        raise NotImplementedError()

    @staticmethod
    def read_bookmarks(f:file) -> 'TagFile':
        raise NotImplementedError()

    def inc(self, key):
        if not bool(key):
            return
        norm_key = self.norm_regex.sub("_", key.strip())
        self.count[norm_key] += 1

    def set_count(self, key:str, value:int):
        if not bool(key):
            return
        norm_key = self.norm_regex.sub("_", key.strip())
        self.count[norm_key] = value

    def __iter__(self):
        return iter(self.count)

    def __str__(self):
        """
        Export the counts, 1 entry per line, as:
        `key` : `value`
        """
        key_sort = sorted(list(self.count.keys()))
        return "\n".join(["{} : {}".format(k, self.count[k]) for k in key_sort])

    def __iadd__(self, values):
        assert(isinstance(value, TagFile))
        for key, value in values.count:
            norm_key = self.norm_regex.sub("_", key.strip())
            self.count[norm_key] += value

    def __len__(self):
        return len(self.count)
    def update(self, values):
        for tag in values:
            self.inc(tag)

    def to_set(self) -> Set[str]:
        return set(self.count.keys())

    def get_count(self, tag):
        norm_tag = self.norm_regex.sub("_", tag.strip())
        return self.count[norm_tag]

    def __contains__(self, value):
        return value in self.count

    def difference(self, other: 'TagFile') -> 'TagFile':
        result = TagFile()
        for tag in other:
            if tag not in self:
                result.set_count(tag, other.get_count(tag))

        return result

@dataclass
class SubstitutionFile(TagFile):
    """ SubstitutionFiles add a replacement tag for some tags """

    ext     : str = field(default=".sub")
    mapping : Dict[str, str] = field(default_factory=lambda: defaultdict(lambda: ""))

    @staticmethod
    def read(f:file) -> 'SubstitutionFile':
        obj = SubstitutionFile()
        for line in f.readlines():
            line_s = [obj.norm_regex.sub("_", x.strip()) for x in line.split(obj.sep)]
            obj.set_count(line_s[0], line_s[1])
            if len(line_s) > 2 and bool(line_s[2]):
                obj.set_sub(line_s[0], line_s[2])

        return obj

    def __str__(self):
        """
        Export the mapping, 1 entry per line, as:
        `key` : `count` : `substitution`
        """
        key_sort = sorted(list(self.count.keys()))
        return "\n".join(["{} : {} : {} ".format(k,
                                                 self.count[k],
                                                 self.mapping[k]) for k in key_sort])

    def __iadd__(self, value):
        assert(isinstance(value, SubstitutionFile))
        for key in value.count:
            self.count[key] += value.count[key]
            if key in value.mapping and key not in self.mapping:
                self.mapping[key] = value.mapping[key]
            elif key in self.mapping and key in value.mapping:
                raise Exception(f"Substitution Conflict for {key}")

    def sub(self, value:str):
        """ apply a substitution if it exists """
        if value in self.mapping:
            return self.mapping[value]

        return value

    def has_sub(self, value):
        return value in self.mapping
    def set_sub(self, key, value):
        if not bool(key):
            return
        self.mapping[key] = value