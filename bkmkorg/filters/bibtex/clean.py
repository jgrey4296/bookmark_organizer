#!/opt/anaconda3/envs/bookmark/bin/python
"""
Script to clean a bibtex file, converting everything to unicode
"""
import argparse
import logging as root_logger
from hashlib import sha256
from math import ceil
from os import listdir, mkdir
from os.path import (abspath, commonpath, exists, expanduser, isdir, isfile,
                     join, realpath, split, splitext)
from shutil import copyfile, move

import bibtexparser as b
import regex as re
from bibtexparser import customization as c
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
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
def expander(path):
    return abspath(expanduser(path))

def safe_splitname(s):
    s = s.strip()
    if s.endswith(","):
        s = s[:-1]
    return c.splitname(s)

def maybe_unicode(record):
    try:
        record = c.convert_to_unicode(record)
    except TypeError as e:
        logging.warning("Unicode Error on: {}".format(record['ID']))
        record['unicode_error'] = str(e)
        record['error'].append("unicode_error")


def check_year(record):
    if 'year' not in record:
        record['year_error'] = "No year"
        record['error'].append('year_error')

def hashcheck_files(record):
    file_set = set()
    try:
        # add md5 of associated files
        file_fields = [x for x in record.keys() if 'file' in x]
        files = [expander(record[x]) for x in file_fields]
        file_set = set(files)
        if not 'hashes' in record:
            hashes = [file_to_hash(x) for x in file_set]
            record['hashes'] = ";".join(hashes)
        else:
            saved_hashes = set(record['hashes'].split(';'))
            hashes = set([file_to_hash(x) for x in file_set])
            if saved_hashes.symmetric_difference(hashes):
                raise Exception("Hash Mismatches", saved_hashes.difference(hashes), hashes.difference(saved_hashes))

    except FileNotFoundError as e:
        logging.warning("File Error: {} : {}".format(record['ID'], e.args[0]))
        record['file_error'] = "File Error: {}".format(e.args[0])
        record['error'].append('file_error')
    except Exception as e:
        logging.warning("Error: {}".format(e.args[0]))
        record['hash_error'] = "{} : / :".format(e.args[0], e.args[1])
        record['error'].append('hash_error')

    return file_set


def move_files_to_library(record, file_set):
    #if file is not in the library common prefix, move it there
    #look for year, then first surname, then copy in, making dir if necessary
    if not bool(file_set):
        return

    for x in file_set:
        try:
            logging.info("Expanding: {}".format(x))
            current_path = x
            common = commonpath([current_path, args.library])
            if common != args.library:
                logging.info("Found file outside library: {}".format(current_path))
                logging.info("Common: {}".format(common))
                #get the author and year
                year = record['year']
                authors = c.getnames([i.strip() for i in record["author"].replace('\n', ' ').split(" and ")])
                authors_split = [safe_splitname(a) for a in authors]
                author_surnames = [a['last'][0] for a in authors_split]
                year_path = join(args.library, year)
                author_path = join(year_path, ", ".join(author_surnames))
                logging.info("New Path: {}".format(author_path))
                #create directory if necessary
                #copy file
                full_new_path = join(author_path, split(current_path)[1])
                logging.info("Copying file")
                logging.info("From: {}".format(current_path))
                logging.info("To: {}".format(full_new_path))
                response = input("Enter to confirm: ")
                if response == "":
                    logging.info("Proceeding")
                    if not exists(year_path):
                        mkdir(year_path)
                    if not exists(author_path):
                        mkdir(author_path)
                    if not exists(full_new_path):
                        copyfile(current_path, full_new_path)
                    move(current_path, "{}__x".format(current_path))
                    file_set.remove(x)
                    file_set.add(full_new_path)
                    record['file'] = ";".join(file_set)

        except Exception as e:
                logging.info("Issue copying file for: {}".format(x))
                logging.info(e)
                record['move_error'] = str(e)
                record['error'].append('move_error')


def clean_tags(record):
    try:
        tags = set()
        if 'tags' in record:
            tags.update([x.strip() for x in record['tags'].split(",")])

        if 'keywords' in record:
            tags.update([x.strip() for x in record['keywords'].split(',')])
            del record['keywords']

        if 'mendeley-tags' in record:
            tags.update([x.strip() for x in record['mendeley-tags'].split(',')])
            del record['mendeley-tags']

        record['tags'] = ",".join(tags)

    except Error as e:
        logging.warning("Tag Error: {}".format(record['ID']))
        record['tag_error'] = str(e)
        record['error'].append('tag_error')


def custom_clean(record):
    record['error'] = []

    maybe_unicode(record)
    check_year(record)
    file_set = hashcheck_files(record)
    # move_files_to_library(record, file_set)
    clean_tags(record)
    return record


if __name__ == "__main__":
    # Setup
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=
                                     "\n".join(["Specify a Target bibtex file,",
                                                "Output file,",
                                                "And the Location of the pdf library.",
                                                "Cleans names and moves all non-library pdfs into the library.",
                                                "Records errors in an 'error' field for an entry."]))

    parser.add_argument('-t', '--target', action='append')
    parser.add_argument('-o', '--output', default="bibtex")
    parser.add_argument('-l', '--library', default="~/MEGA/pdflibrary")
    args = parser.parse_args()

    assert(exists(args.target))

    logging.info("Targeting: {}".format(args.target))
    logging.info("Output to: {}".format(args.output))

    bib_files = retrieval.get_data_files(args.target, ".bib")
    db        = BU.parse_bib_files(bib_files, func=custom_clean)

    #Get errors and write them out:
    errored   = [x for x in db.entries if 'error' in x and bool(x['error'])]
    error_tuples = [(x['ID'], x[y]) for x in errored for y in x['error']]
    formatted = "\n".join(["{} : {}".format(x, y) for x,y in error_tuples])

    with open('{}.errors'.format(args.output), 'a') as f:
        f.write(formatted)

    # Write out the actual bibtex
    writer = BibTexWriter()
    with open(args.output,'w') as f:
        f.write(writer.write(db))