"""
Script to Process Bibtex, bookmark, and org files for tags
and to clean them
"""
from bibtexparser import customization as c
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bkmkorg.bookmark_data import bookmarkTuple
from bkmkorg.io.export_netscape import exportBookmarks
from bkmkorg.io.import_netscape import open_and_extract_bookmarks
from math import ceil
from os import listdir
from os.path import join, isfile, exists, isdir, splitext, expanduser, abspath, split
import argparse
import bibtexparser as b
import logging as root_logger
import regex
import regex as re

from bkmkorg.utils import retrieval
from bkmkorg.utils import bibtex as BU
from bkmkorg.utils import tags as TU

logging = root_logger.getLogger(__name__)

##############################
#see https://docs.python.org/3/howto/argparse.html
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="\n".join(["Extracts all tags in all bibtex, bookmark and org files in specified dirs"]))
parser.add_argument('-t', '--target',action="append")
parser.add_argument('-c', '--cleaned', action="append")

bparser = BibTexParser(common_strings=False)
bparser.ignore_nonstandard_types = False
bparser.homogenise_fields = True

def custom(record):
    # record = c.type(record)
    # record = c.author(record)
    # record = c.editor(record)
    # record = c.journal(record)
    # record = c.keyword(record)
    # record = c.link(record)
    # record = c.doi(record)
    tags = set()

    if 'tags' in record:
        tags.update([i.strip() for i in re.split(',|;', record["tags"].replace('\n', ''))])
    if "keywords" in record:
        tags.update([i.strip() for i in re.split(',|;', record["keywords"].replace('\n', ''))])
    if "mendeley-tags" in record:
        tags.update([i.strip() for i in re.split(',|;', record["mendeley-tags"].replace('\n', ''))])

    record['tags'] = tags
    # record['p_authors'] = []
    # if 'author' in record:
    #     record['p_authors'] = [c.splitname(x, False) for x in record['author']]
    return record



#--------------------------------------------------
if __name__ == "__main__":
    logging.info("Tag Cleaning start: --------------------")
    LOGLEVEL = root_logger.DEBUG
    LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
    root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

    console = root_logger.StreamHandler()
    console.setLevel(root_logger.INFO)
    root_logger.getLogger('').addHandler(console)
    logging = root_logger.getLogger(__name__)

    args = parser.parse_args()

    logging.info("Targeting: {}".format(args.target))
    logging.info("Cleaning based on: {}".format(args.cleaned))

    #Load Cleaned Tags
    tag_sub_files = retrieval.get_data_files(args.cleaned, [".org", ".txt", ".tags"])
    cleaned_tags = retrieval.read_raw_tags(tag_sub_files)
    logging.info("Loaded {} tag substitutions".format(len(cleaned_tags)))

    #Load Bibtexs, html, orgs and clean each
    bibs, htmls, orgs = retrieval.collect_files(args.target)
    retrieval.clean_bib_files(bibs   , cleaned_tags)
    retrieval.clean_org_files(orgs   , cleaned_tags)
    retrieval.clean_html_files(htmls , cleaned_tags)
    logging.info("Complete --------------------")
