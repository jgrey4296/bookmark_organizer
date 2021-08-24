#!/opts/anaconda3/envs/ENV/python
import argparse
import logging as root_logger
from os import listdir
from os.path import (abspath, exists, expanduser, isdir, isfile, join, split,
                     splitext)
from typing import (Any, Callable, ClassVar, Dict, Generic, Iterable, Iterator,
                    List, Mapping, Match, MutableMapping, Optional, Sequence,
                    Set, Tuple, TypeVar, Union, cast)

import bibtexparser as b
import regex as re
from bibtexparser import customization as c
from bibtexparser.bparser import BibTexParser
from bkmkorg.utils.bibtex import parsing as BU
from bkmkorg.utils.file import retrieval

LOGLEVEL = root_logger.DEBUG
LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

console = root_logger.StreamHandler()
console.setLevel(root_logger.INFO)
root_logger.getLogger('').addHandler(console)
logging = root_logger.getLogger(__name__)
##############################
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog="\n".join(["Describe a bibtex file's:",
                                                    "Tags, year counts, authors,",
                                                    "And entries lacking files or with multiple files"]))
parser.add_argument('-t', '--target', default="~/github/writing/resources/bibliography", help="Input target")
parser.add_argument('-o', '--output', default="authors.list",                            help="Output Target")
parser.add_argument('-c', '--counts', action="store_true")

def custom(record):
    record = c.author(record)
    record = c.editor(record)
    return record


def process_db(db) -> List[str]:
    """ Extract all authors mentioned """
    result     = set()
    count      = 0
    proportion = int(len(db.entries) / 10)

    for i, entry in enumerate(db.entries):
        # Log progress
        if i % proportion == 0:
            logging.info(f"{count}/10 Complete")
            count += 1

        if 'author' in entry:
            result.update(entry['author'])

        if 'editor' in entry:
            result.update([x['name'] for x in entry['editor']])

    return sorted(result)

def main():
    args = parser.parse_args()

    args.output = abspath(expanduser(args.output))
    assert(exists(args.target))

    logging.info("Targeting: {}".format(args.target))
    logging.info("Output to: {}".format(args.output))

    # Load targets
    bib_files = retrieval.get_data_files(args.target, ".bib")
    db = BU.parse_bib_files(bib_files, func=custom)
    logging.info("Bibtex loaded")

    logging.info(f"Processing Entries: {len(db.entries)}")
    result = process_db(db)

    # write the output
    with open(args.output, 'w') as f:
        f.write("\n".join(result))

    logging.info("Complete")

if __name__ == '__main__':
    main()
