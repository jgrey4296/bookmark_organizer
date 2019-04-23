"""
Compare 2 bibtex files
"""

from bibtexparser import customization as c
from bibtexparser.bparser import BibTexParser
from math import ceil
from os import listdir
from os.path import join, isfile, exists, isdir, splitext, expanduser, abspath
import argparse
import bibtexparser as b
import regex as re
# Setup root_logger:
from os.path import splitext, split
import logging as root_logger
LOGLEVEL = root_logger.DEBUG
LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

console = root_logger.StreamHandler()
console.setLevel(root_logger.INFO)
root_logger.getLogger('').addHandler(console)
logging = root_logger.getLogger(__name__)


parser = argparse.ArgumentParser("")
parser.add_argument('-t', '--target', action='append')
args = parser.parse_args()

args.target = [abspath(expanduser(x)) for x in args.target]

logging.info("Targeting: {}".format(args.target))

all_dbs = []
for t in args.target:
    parser = BibTexParser(common_strings=False)
    parser.ignore_nonstandard_types = False
    parser.homogenise_fields = True

    with open(t, 'r') as f:
        db = b.load(f, parser)
    all_dbs.append(db)

logging.info("DB Sizes: {}".format(", ".join([str(len(x.entries)) for x in all_dbs])))

sorted_dbs = sorted([(len(x.entries), x) for x in all_dbs] ,reverse=True)

head = sorted_dbs[0][1]
rst = sorted_dbs[1:]
head_set = set([x['ID'] for x in head.entries])

missing_keys = set([])
for _,db in rst:
    db_set = set([x['ID'] for x in db.entries])
    if head_set.issuperset(db_set):
        continue


    missing_keys.update(db_set.difference(head_set))


logging.info("{} Keys missing from master: {}".format(len(missing_keys), "\n".join(missing_keys)))
