#!/opt/anaconda3/envs/bookmark/bin/python
"""
Integrate new bookmarks into the main bookmark file
"""
import argparse
import logging as root_logger
from os.path import abspath, exists, expanduser, split, splitext

from bkmkorg.io.writer.netscape import exportBookmarks as html_export
from bkmkorg.io.writer.org import exportBookmarks as org_export
from bkmkorg.io.reader.netscape import open_and_extract_bookmarks
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
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog = "\n".join(["Find all bookmarks in {source} files and create a master {output} html"]))
parser.add_argument('-s', '--sources', action='append')
parser.add_argument('-o', '--output')


if __name__ == "__main__":
    args = parser.parse_args()

    source_files = retrieval.get_data_files(args.sources, ".html")

    # Exit if not targeting a bookmark file
    if splitext(args.output)[1] != ".html":
        raise Exception("Html not specified for output")

    # Ask to overwrite output file
    if exists(args.output) and args.output not in source_files:
        logging.warning("Ouput already exists: {}".format(args.output))
        logging.warning("Output is not in source targets")
        response = input("Overwrite? Y/*: ")
        if response != "Y":
            logging.info("Cancelling")
            exit()

    #load the sources
    bkmk_dict = {}

    for loc in source_files:
        logging.info("Dict Length: {}".format(len(bkmk_dict)))
        logging.info("Opening: {}".format(loc))
        source_bkmks = open_and_extract_bookmarks(loc)
        for x in source_bkmks:
            #combine without duplicating
            if x.url not in bkmk_dict:
                bkmk_dict[x.url] = x
                continue
            bkmk_dict[x.url].tags.update(x.tags)

    #write out
    logging.info("Writing out: {}".format(len(bkmk_dict)))
    html_export(list(bkmk_dict.values()), args.output)
