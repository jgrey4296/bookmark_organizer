#!/usr/bin/env python3
"""

"""
##############################
# IMPORTS
####################
import argparse
import logging as root_logger
import random
from collections import defaultdict
from os import listdir, remove
from os.path import (abspath, exists, expanduser, isdir, isfile, join, split,
                     splitext)
import sys
from subprocess import run
from time import sleep
from typing import (Any, Callable, ClassVar, Dict, Generic, Iterable, Iterator,
                    List, Mapping, Match, MutableMapping, Optional, Sequence,
                    Set, Tuple, TypeVar, Union, cast)

from bkmkorg.utils.dfs import files as retrieval
from bkmkorg.utils.tag.collection import TagFile

# Setup root_logger:
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
                                 epilog = "\n".join(["Tag Grep",
                                                     "Use existing tags to index potential org files"]))
parser.add_argument('-l', '--library', action="append")
parser.add_argument('-t', '--target', action="append")
parser.add_argument('-o', '--output')
parser.add_argument('--file_batch', default=100, type=int)
parser.add_argument('--tag_batch',  default=100, type=int)

def main():
    logging.info("Grepping for Tags")
    args = parser.parse_args()
    args.output = abspath(expanduser(args.output))

    # Collect files to process
    lib         = retrieval.get_data_files(args.library, ext=".org")
    # Get tag set
    tags           = TagFile.builder(args.target)
    match_dict     = defaultdict(lambda: list())
    batch_count    = int(len(lib) / args.file_batch)
    processed_tags = set()

    # fail out if a lock file exists
    if exists(args.output + ".lock"):
        logging.warning("Lock File Exists")
        sys.exit()

    open(args.output + ".lock", 'w').close()
    assert(exists(args.output + ".lock"))

    # Ignore already checked tags
    if exists(args.output):
        with open(args.output, 'r') as f:
            lines = f.readlines()
        logging.debug(f"Index file: {len(lines)} lines")
        for line in lines:
            processed_tags.add(line.split(":")[0].strip())

    remaining_keys = list(set(tags.count.keys()).difference(processed_tags))
    logging.info(f"Total/Processed/Remaining: {len(tags)}/{len(processed_tags)}/{len(remaining_keys)}")
    logging.debug(f"Processed: {processed_tags}")
    for i, tag in enumerate(remaining_keys[:args.tag_batch]):
        cleaned_tag = tag.replace("_", " ")
        ## batch filter files that mention the tag
        logging.info(f"-- Tag: {tag} {i}/{len(tags)}")
        batch_num = 0
        for start in range(0, len(lib), args.file_batch):
            logging.info(f"File Batch: {batch_num}/{batch_count}")
            result = run(['grep' , '-l', cleaned_tag, *lib[start:start+args.file_batch]], capture_output=True)
            if result.returncode == 0 and bool(result.stdout):
                to_add : List = [x.strip() for x in result.stdout.decode().split("\n")]
                shortened = [x[len(args.target[0]):] if args.target[0] in x else x for x in to_add]
                match_dict[tag] += shortened

            batch_num += 1

        # save file list in tag file
        if bool(match_dict):
            logging.info("Writing to file")
            lines = (["{} : {} : {}".format(x, len(y), ":".join(y)) for x,y in match_dict.items() if bool(y)])
            logging.debug(f"Output Lines: {len(lines)}")
            output_text = "\n".join(lines)
            with open(args.output,'a') as f:
                f.write("\n")
                f.write(output_text)

            match_dict.clear()

    remove(args.output + ".lock")
    logging.info("Finished")

########################################
if __name__ == "__main__":
    main()