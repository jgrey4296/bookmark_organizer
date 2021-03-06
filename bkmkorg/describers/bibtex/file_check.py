#!/opt/anaconda3/envs/bookmark/bin/python
"""
Check Bibtex library against pdf library
Output bibtex entries without matching files,
and files without matching entries
"""
import argparse
import logging as root_logger
import re
from os import listdir
from os.path import abspath, expanduser, isdir, join, split, splitext
from unicodedata import normalize

import bibtexparser as b
from bibtexparser import customization as c

from bkmkorg.utils.bibtex import parsing as BU
from bkmkorg.utils.file import retrieval

PATH_NORM = re.compile("^.+?pdflibrary")
FILE_RE   = re.compile("^file(\d*)")

# Setup
LOGLEVEL      = root_logger.DEBUG
LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

console = root_logger.StreamHandler()
console.setLevel(root_logger.INFO)
root_logger.getLogger('').addHandler(console)
logging = root_logger.getLogger(__name__)


parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog="\n".join(["Check All pdfs are accounted for in a bibliography"])
                                    )
parser.add_argument('-t', '--target',  help="Pdf Library directory to verify")
parser.add_argument('-l', '--library', help="Bibtex Library directory to verify")
parser.add_argument('-o', '--output',  help="Output location for reports")


if __name__ == "__main__":
    args = parser.parse_args()

    args.output = abspath(expanduser(args.output))
    assert(isdir(args.library))
    assert(isdir(args.output))
    assert(isdir(args.target))

    # Get targets
    all_bibs = retrieval.get_data_files(args.library, ".bib")
    main_db = BU.parse_bib_files(all_bibs)

    logging.info("Loaded Database: {} entries".format(len(main_db.entries)))
    count              = 0
    all_file_mentions  = []
    all_existing_files = retrieval.get_data_files(args.target, [".epub", ".pdf"], normalize=True)

    # Convert entries to unicode
    for i, entry in enumerate(main_db.entries):
        if i % 10 == 0:
            logging.info("{}/10 Complete".format(count))
            count += 1
        unicode_entry = b.customization.convert_to_unicode(entry)

        entry_keys = [x for x in unicode_entry.keys() if FILE_RE.search(x)]
        for k in entry_keys:
            all_file_mentions.append(normalize('NFD', unicode_entry[k]))


    logging.info("Found {} files mentioned in bibliography".format(len(all_file_mentions)))
    logging.info("Found {} files existing".format(len(all_existing_files)))

    logging.info("Normalizing paths")
    norm_mentions = set([])
    # Normalise all paths in bibtex entries
    for x in all_file_mentions:
        path = PATH_NORM.sub("", x)
        if path in norm_mentions:
            logging.info("Duplicate file mention: {}".format(path))
        else:
            norm_mentions.add(path)

    norm_existing = set([])
    # Remove duplicates mentions
    for x in all_existing_files:
        path = PATH_NORM.sub("", x)
        if path in norm_existing:
            logging.info("Duplicate file existence: {}".format(path))
        else:
            norm_existing.add(path)

    logging.info("Normalized paths")

    mentioned_non_existent = norm_mentions - norm_existing
    existing_not_mentioned = norm_existing - norm_mentions

    logging.info("Mentioned but not existing: {}".format(len(mentioned_non_existent)))
    logging.info("Existing but not mentioned: {}".format(len(existing_not_mentioned)))

    # Create output files

    with open(join(args.output, "bibtex.not_existing"),'w') as f:
        f.write("\n".join(mentioned_non_existent))

    with open(join(args.output, "bibtex.not_mentioned"), 'w') as f:
        f.write("\n".join(existing_not_mentioned))
