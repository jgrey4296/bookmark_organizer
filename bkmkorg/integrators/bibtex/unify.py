"""
Script to combine multiple bibtex files into one
"""
import argparse
import logging as root_logger
from math import ceil
from os import listdir, mkdir
from os.path import (abspath, exists, expanduser, isdir, isfile, join, split,
                     splitext)

import bibtexparser as b
import regex as re

from bibtexparser import customization as c
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter

from bkmkorg.utils.bibtex import parsing as BU
from bkmkorg.utils.file import retrieval

# Setup
LOGLEVEL = root_logger.DEBUG
LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

console = root_logger.StreamHandler()
console.setLevel(root_logger.INFO)
root_logger.getLogger('').addHandler(console)
logging = root_logger.getLogger(__name__)
##############################

#see https://docs.python.org/3/howto/argparse.html
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog="""Integrates a collection of bibtex files into a single file. Targets can be flat directories""")
parser.add_argument('-t', '--target', action="append")
parser.add_argument('-o', '--output', default="./output/integrated.bib")


def custom(record):
    # record = c.type(record)
    # record = c.author(record)
    # record = c.editor(record)
    # record = c.journal(record)
    # record = c.keyword(record)
    # record = c.link(record)
    # record = c.doi(record)
    # if "keywords" in record:
    #     record["keywords"] = [i.strip() for i in re.split(',|;', record["keywords"].replace('\n', ''))]
    # if "mendeley-tags" in record:
    #     record["mendeley-tags"] = [i.strip() for i in re.split(',|;', record["mendeley-tags"].replace('\n', ''))]

    # record['p_authors'] = []
    # if 'author' in record:
    #     record['p_authors'] = [c.splitname(x, False) for x in record['author']]
    return record



if __name__ == "__main__":
   args = parser.parse_args()
    args.output = abspath(expanduser(args.output))

    logging.info("Targeting: {}".format(args.target))
    logging.info("Output to: {}".format(args.output))

    #load each of the specified files
    target_files = retrieval.get_data_files(args.target, ".bib")
    dbs = [BU.parse_bib_files(x, custom) for x in target_files]

    main_db = b.bibdatabase.BibDatabase()
    # Load the main database
    if exists(args.output):
        BU.parse_bib_files(args.output, custom, databse=main_db)

    main_set = set(main_db.get_entry_dict().keys())
    total_entries = main_db.entries[:]
    missing_keys_main = set()

    # Get entries missing from the main database
    for db in dbs:
        db_dict = db.get_entry_dict()
        db_set = set(db_dict.keys())
        missing_keys = db_set.difference(main_set)
        missing_keys_main.update(missing_keys)
        total_entries += [db_dict[x] for x in missing_keys]

    logging.info("{} missing entries".format(len(total_entries)))
    main_db.entries = total_entries

    # Write out the combined database
    logging.info("Bibtex loaded")
    writer = BibTexWriter()
    writer.align_values = True
    with open(join(args.output),'a') as f:
        f.write(writer.write(main_db))
