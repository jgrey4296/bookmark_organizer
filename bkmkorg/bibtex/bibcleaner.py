"""
Script to clean a bibtex file, converting everything to unicode
"""
import IPython
import bibtexparser as b
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser import customization as c
from os.path import join, isfile, exists, isdir, splitext, expanduser, abspath, commonpath, realpath
from os import listdir, mkdir
from hashlib import sha256
from shutil import copyfile
import regex as re
from math import ceil
import argparse
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
##############################

#see https://docs.python.org/3/howto/argparse.html
parser = argparse.ArgumentParser("")
parser.add_argument('-t', '--target', default="~/Mega/library.bib")
parser.add_argument('-o', '--output', default="bibtex")
parser.add_argument('-l', '--library', default="~/MEGA/Mendeley")
args = parser.parse_args()

args.target = realpath(abspath(expanduser(args.target)))
args.library = realpath(abspath(expanduser(args.library)))
assert(exists(args.target))

logging.info("Targeting: {}".format(args.target))
logging.info("Output to: {}".format(args.output))

parser = BibTexParser(common_strings=False)
parser.ignore_nonstandard_types = False
parser.homogenise_fields = True

def make_bar(k, v, left_pad_v, right_scale_v):
    pad = ((10 + left_pad_v) - len(k))
    bar = ceil(((100 - pad) / right_scale_v) * v)
    full_str = "{}{}({}) : {}>\n".format(k, " " * pad, v, "=" *  bar)
    return full_str

def file_to_hash(filename):
    if not isfile(filename):
        raise Exception(filename)
    with open(filename, 'rb') as f:
        return sha256(f.read()).hexdigest()

def add_slash_if_necessary(x):
    if x[0] != '/':
        x = '/' + x
    return x.strip()

def custom(record):
    try:
        record = c.convert_to_unicode(record)
    except TypeError as e:
        logging.warning("Unicode Error on: {}".format(record['ID']))
        record['error'] = 'unicode'

    try:
        #add md5 of associated files
        files = [add_slash_if_necessary(y) for x in record['file'].split(';') for y in x.split(':') if bool(y.strip()) and y.strip().lower() != 'pdf']
        file_set = set(files)
        if not 'hashes' in record:
            hashes = [file_to_hash(x) for x in file_set]
            record['hashes'] = ";".join(hashes)
            #regularize format of files list
            record['file'] = ";".join(file_set)
    except Exception as e:
        logging.warning("File Error: {} : {}".format(record['ID'], e.args[0]))
        record['error'] = 'file'

    #todo: if file is not in the library common prefix, move it there
    #look for year, then first surname, then copy in, making dir if necessary
    if file_set:
        for x in file_set:
            try:
                current_path = realpath(x)
                common = commonpath([current_path, args.library])
                if common != args.library:
                    logging.info("Found file outside library: {}".format(current_path))
                    logging.info("Common: {}".format(common))
                    #get the author and year
                    year = record['year']
                    authors = c.getnames([i.strip() for i in record["author"].replace('\n', ' ').split(" and ")])
                    authors_split = [c.splitname(a) for a in authors]
                    author_surnames = [a['last'][0] for a in authors_split]
                    new_path = join(args.library, year, ", ".join(author_surnames))
                    logging.info("New Path: {}".format(new_path))
                    #create directory if necessary
                    #copy file
                    full_new_path = join(new_path, split(current_path)[1])
                    logging.info("Copying file")
                    logging.info("From: {}".format(current_path))
                    logging.info("To: {}".format(full_new_path))
                    response = input("Enter to confirm: ")
                    if response == "":
                        logging.info("Proceeding")
                        if not exists(new_path):
                            mkdir(new_path)
                        if exists(full_new_path):
                            raise Exception("File already exists")
                        copyfile(x, full_new_path)
                        file_set.remove(x)
                        file_set.add(full_new_path)
                        record['file'] = ";".join(file_set)
            except Exception as e:
                logging.info("Issue copying file for: {}".format(x))
                logging.info(e)
                record['error'] = 'file_copy'


    #regularize keywords
    try:
        keywords = set()
        if 'tags' not in record:
            if 'keywords' in record:
                keywords.update([x.strip() for x in record['keywords'].split(',')])
                del record['keywords']
            if 'mendeley-tags' in record:
                keywords.update([x.strip() for x in record['mendeley-tags'].split(',')])
                del record['mendeley-tags']

            record['tags'] = ",".join(keywords)
    except Error as e:
        logging.warning("Tag Error: {}".format(record['ID']))
        record['error'] = 'tag'

    # record = c.type(record)
    # record = c.author(record)
    # record = c.editor(record)
    # record = c.journal(record)
    # record = c.keyword(record)
    # record = c.link(record)
    # record = c.doi(record)
    # record['p_authors'] = []
    # if 'author' in record:
    #     record['p_authors'] = [c.splitname(x, False) for x in record['author']]
    return record

parser.customization = custom

with open(args.target, 'r') as f:
    logging.info("Loading bibtex")
    db = b.load(f, parser)
logging.info("Bibtex loaded")

#Get errors and write them out:
errored = [x for x in db.entries if 'error' in x]

with open('{}.errors'.format(args.output), 'w') as f:
    f.write("\n".join(["{} : {}".format(x['ID'], x['error']) for x in errored]))

writer = BibTexWriter()
with open(args.output,'w') as f:
        f.write(writer.write(db))