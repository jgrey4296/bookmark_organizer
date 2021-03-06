"""
Script to read org files and check them for erroneous tags
"""
import argparse
import logging as root_logger
from math import ceil
from os import listdir
from os.path import (abspath, exists, expanduser, isdir, isfile, join, split,
                     splitext)

import bibtexparser as b
import regex
import regex as re
from bibtexparser import customization as c
from bibtexparser.bparser import BibTexParser

from bkmkorg.io.reader.netscape import open_and_extract_bookmarks
from bkmkorg.utils.bibtex import parsing as BU
from bkmkorg.utils.file import retrieval

LOGLEVEL = root_logger.DEBUG
LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

console = root_logger.StreamHandler()
console.setLevel(root_logger.INFO)
root_logger.getLogger('').addHandler(console)
logging = root_logger.getLogger(__name__)
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="\n".join(["Report org files with incorrect meta data of tweets"]))
parser.add_argument('-t', '--target',action="append")
parser.add_argument('-o', '--output', default="collected")
#--------------------------------------------------


if __name__ == "__main__":
    logging.info("Org Check start: --------------------")
    args = parser.parse_args()
    args.output = abspath(expanduser(args.output))

    logging.info("Targeting: {}".format(args.target))
    logging.info("Output to: {}".format(args.output))

    bibs, htmls, orgs = retrieval.collect_files(args.target)
    suspect_files = retrieval.check_orgs(orgs)

    logging.info("Found {} suspect files".format(len(suspect_files)))
    with open(args.output,'w') as f:
        for id_str in suspect_files:
            f.write("{}\n".format(id_str))

    logging.info("Complete --------------------")
