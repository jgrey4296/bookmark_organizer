"""
Script to Process Bibtex, bookmark, and org files for tags
and to collect them
"""
import argparse
import logging as root_logger
import re
from os import mkdir
from os.path import abspath, expanduser, isdir, join, split, splitext

from bibtexparser import customization as c

from bkmkorg.io.import.import_netscape import open_and_extract_bookmarks
from bkmkorg.utils.bibtex import parsing as BU
from bkmkorg.utils.file import retrieval
from bkmkorg.utils.tags import tags as TU

# Setup logger
LOGLEVEL = root_logger.DEBUG
LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

console = root_logger.StreamHandler()
console.setLevel(root_logger.INFO)
root_logger.getLogger('').addHandler(console)
logging = root_logger.getLogger(__name__)



##############################
def custom(record):
    record = c.type(record)
    record = c.author(record)
    record = c.editor(record)
    record = c.journal(record)
    record = c.keyword(record)
    record = c.link(record)
    record = c.doi(record)
    tags = set()

    if 'tags' in record:
        tags.update([i.strip() for i in re.split(',|;', record["tags"].replace('\n', ''))])
    if "keywords" in record:
        tags.update([i.strip() for i in re.split(',|;', record["keywords"].replace('\n', ''))])
    if "mendeley-tags" in record:
        tags.update([i.strip() for i in re.split(',|;', record["mendeley-tags"].replace('\n', ''))])

    record['tags'] = tags
    record['p_authors'] = []
    if 'author' in record:
        record['p_authors'] = [c.splitname(x, False) for x in record['author']]
    return record





if __name__ == "__main__":
    # Setup
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="\n".join(["Extracts all tags in all bibtex, bookmark and org files in specified dirs"]))
    parser.add_argument('-t', '--target',action="append")
    parser.add_argument('-o', '--output', default="collected")
    parser.add_argument('-c', '--cleaned', action="append")

    logging.info("Tag Collation start: --------------------")
    cli_args = parser.parse_args()
    cli_args.output = abspath(expanduser(cli_args.output))

    logging.info("Targeting: {}".format(cli_args.target))
    if isdir(cli_args.output) and not exists(cli_args.output):
        mkdir(cli_args.output)
    if isdir(cli_args.output):
        cli_args.output = join(cli_args.output, "tags")
    logging.info("Output to: {}".format(cli_args.output))
    logging.info("Cleaned Tags locations: {}".format(cli_args.cleaned))

    bibs, htmls, orgs = retrieval.collect_files(cli_args.target)
    bib_db    = BU.parse_bib_files(bibs, func=custom)
    bib_tags  = TU.extract_tags_from_bibtex(bib_db)
    org_tags  = TU.extract_tags_from_org_files(orgs)
    html_tags = TU.extract_tags_from_html_files(htmls)
    all_tags  = TU.combine_all_tags([bib_tags, org_tags, html_tags])

    TU.write_tags(bib_tags, cli_args.output + "_bib")
    TU.write_tags(org_tags, cli_args.output + "_orgs")
    TU.write_tags(html_tags, cli_args.output + "_htmls")
    TU.write_tags(all_tags, cli_args.output)
    logging.info("Complete --------------------")

    if not bool(cli_args.cleaned):
        exit()

    # load existing tag files
    cleaned_files = retrieval.get_data_files(cli_args.cleaned, [".txt", ".tags", ".org"])
    cleaned = retrieval.read_substitutions(cleaned_files)

    # get new tags
    tags = set(all_tags.keys())
    ctags = set(cleaned.keys())
    new_tags = tags - ctags

    new_tag_dict = {x : all_tags[x] for x in new_tags}
    # group them separately, alphabeticaly
    # To be included in the separate tag files
    TU.write_tags(new_tag_dict, cli_args.output + "_new_tags")