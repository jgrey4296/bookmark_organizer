#!~/anaconda/envs/bookmark/bin/python

# load bibtex, graph tags by year, all entries by year,

import argparse
import logging as root_logger
from collections import defaultdict
from datetime import datetime
from os import listdir
from os.path import (abspath, exists, expanduser, isdir, isfile, join, split,
                     splitext)
from typing import (Any, Callable, ClassVar, Dict, Generic, Iterable, Iterator,
                    List, Mapping, Match, MutableMapping, Optional, Sequence,
                    Set, Tuple, TypeVar, Union, cast)

import bibtexparser as b
from bibtexparser import customization as c
from bibtexparser.bparser import BibTexParser
from matplotlib import pyplot as plt

from bkmkorg.utils.bibtex import parsing as BU
from bkmkorg.utils.file import retrieval
from bkmkorg.utils import diagram as DU

# Setup root_logger:
LOGLEVEL = root_logger.DEBUG
LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

console = root_logger.StreamHandler()
console.setLevel(root_logger.INFO)
root_logger.getLogger('').addHandler(console)
logging = root_logger.getLogger(__name__)
##############################
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog = "\n".join(["Create graphs of Bibtex Files"]))
parser.add_argument('--library', action="append", help="The bibtex file collection directory")
parser.add_argument('--target', help="The output target directory")
parser.add_argument('--tag', help="Optional Focus Tag")


def custom_parse(record):
    if 'year' not in record:
        year_temp = "2020"
    else:
        year_temp = record['year']
    if "/" in year_temp:
        year_temp = year_temp.split("/")[0]

    year = datetime.strptime(year_temp, "%Y")
    tags = []
    if 'tags' in record:
        tags = [x.strip() for x in record['tags'].split(",")]

    record['year'] = year
    record['tags'] = tags

    return record

def get_tag_across_years(db, tag) -> List[Tuple[datetime, int]]:
    """
    Find the earliest instance of the tag,
    then track counts from that year onwards
    """
    results_dict : Dict[datetime, int] = defaultdict(lambda: 0)
    for entry in db.entries:
        year = entry['year']
        if tag in entry['tags']:
            results_dict[year] += 1


    return sorted(results_dict.items(), key=lambda x: x[0])

def get_entries_across_years(db) -> List[Tuple[datetime, int]]:
    results_dict : Dict[datetime, int] = defaultdict(lambda: 0)
    for entry in db.entries:
        year = entry['year']
        results_dict[year] += 1

    return sorted(results_dict.items(), key=lambda x: x[0])


if __name__ == "__main__":
    args = parser.parse_args()
    args.library = [abspath(expanduser(x)) for x in args.library]
    args.target = abspath(expanduser(args.target))

    all_bibs = retrieval.get_data_files(args.library, ".bib")
    logging.info("Found {} bib files".format(len(all_bibs)))
    db = b.bibdatabase.BibDatabase()
    BU.parse_bib_files(all_bibs, func=custom_parse, database=db)
    logging.info("Loaded bibtex entries: {}".format(len(db.entries)))

    # Graph tags over time
    year_counts = []
    if args.tag:
        year_counts = get_tag_across_years(db, args.tag)
    else:
        year_counts: List[Tuple[datetime, int]] = get_entries_across_years(db)

    year_counts = [x for x in year_counts if x[1] > 5]
    # chart the tweets
    to_draw = [("Years", year_counts)]
    # n_rows = int(len(to_draw) / 2)
    # n_cols = int(len(to_draw) / 2)
    n_rows = 1
    n_cols = 1
    for count, paired in enumerate(to_draw):
        name, data = paired
        logging.info("Drawing {}".format(name))
        x = [x[0] for x in data]
        y = [x[1] for x in data]
        plt.subplot(n_rows, n_cols, count + 1)
        plt.scatter(x, y, alpha=0.3)
        plt.title(name)
        plt.gcf().autofmt_xdate()

    logging.info("Finished, saving")
    plt.savefig(args.target)
    plt.show()
