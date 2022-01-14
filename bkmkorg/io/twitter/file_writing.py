from typing import List, Set, Dict, Tuple, Optional, Any
from typing import Callable, Iterator, Union, Match
from typing import Mapping, MutableMapping, Sequence, Iterable
from typing import cast, ClassVar, TypeVar, Generic

import datetime
from collections import defaultdict
import json
import logging as root_logger
import uuid
from os import listdir, mkdir
from os.path import (abspath, exists, expanduser, isdir, isfile, join, split,
                     splitext)
from shutil import copyfile, rmtree

import networkx as nx
from bkmkorg.utils.dfs.twitter import dfs_chains
from bkmkorg.utils.download.twitter import download_tweets
from bkmkorg.utils.download.media import download_media
from bkmkorg.utils.twitter.todo_list import TweetTodoFile
from bkmkorg.utils.twitter.tweet_component import TweetComponent
from bkmkorg.utils.twitter.user_summary import TwitterUserSummary
from bkmkorg.utils.twitter.org_writer import TwitterOrg

logging = root_logger.getLogger(__name__)

# TODO could refactor output into template files, ie: jinja.

def construct_component_files(components, tweet_dir, component_dir, twit_graph, twit=None):
    """ Create intermediate component files of tweet threads """
    logging.info("Creating {} component files\n\tfrom: {}\n\tto: {}".format(len(components), tweet_dir, component_dir))
    with TweetComponent(component_dir, components) as id_map:
        # create separate component files
        logging.info("Copying to component files")
        json_files = [join(tweet_dir, x) for x in listdir(tweet_dir) if splitext(x)[1] == ".json"]
        for jfile in json_files:
            with open(jfile, 'r') as f:
                data = json.load(f, strict=False)

            for tweet in data:
                # Add tweet to any of its components
                id_str = tweet['id_str']
                id_map.add(tweet, id_str)

                # Add tweet to any component that quotes it
                quoters = twit_graph.get_quoters(id_str)
                id_map.add(tweet, *quoters)

        if bool(id_map.missing):
            logging.info("Missing: {}".format(id_map.missing))
            if not download_tweets(twit, tweet_dir, id_map.missing):
                exit()


def construct_user_summaries(component_dir, combined_threads_dir, total_users):
    """ collate threads together by originating user """
    logging.info("Constructing summaries\n\tfrom: {} \n\tto: {}".format(component_dir, combined_threads_dir))
    user_lookup = total_users
    # Create final orgs, grouped by head user
    components = [join(component_dir, x) for x in listdir(component_dir) if splitext(x)[1] == ".json"]
    for comp in components:
        logging.info("Constructing Summary for: {}".format(comp))
        # read comp
        with open(comp, 'r') as f:
            data = json.load(f, strict=False)

        if not bool(data):
            continue

        # Get leaves
        tweets      = {x['id_str'] : x for x in data}
        user_counts = defaultdict(lambda: 0)
        for x in data:
            user_counts[x['user']['id_str']] += 1

        head_user   = max(user_counts.items(), key=lambda x: x[1])[0]
        screen_name = str(head_user)
        if head_user in user_lookup:
            screen_name = user_lookup[head_user]['screen_name']

        logging.info("Constructing graph")
        graph     = nx.DiGraph()
        quotes    = set()
        roots     = set()
        for tweet in data:
            if tweet['in_reply_to_status_id_str'] is not None:
                graph.add_edge(tweet['in_reply_to_status_id_str'], tweet['id_str'])
            else:
                graph.add_node(tweet['id_str'])
                roots.add(tweet['id_str'])

            if 'quoted_status_id_str' in tweet and tweet['quoted_status_id_str'] is not None:
                quotes.add(tweet['quoted_status_id_str'])

        # dfs to get longest chain
        chains = []

        if bool(roots):
            chains = dfs_chains(graph, roots)

        if not bool(chains):
            chains = [list(roots.union(quotes))]

        # Assign main thread
        main_thread = max(chains, key=lambda x: len(x))
        main_set    = set(main_thread)
        main_index  = chains.index(main_thread)

        # assign secondary conversations
        rest = chains[:main_index] + chains[main_index+1:]

        rest         = [x for x in rest if bool(x)]
        cleaned_rest = []
        for thread in rest:
            cleaned = [x for x in thread if x not in main_set]
            cleaned_rest.append(cleaned)
            main_set.update(cleaned)

        # create user file if not exist
        summary = TwitterUserSummary(screen_name,
                                     combined_threads_dir)

        if summary.user is None:
            if head_user in user_lookup:
                summary.set_user(user_lookup[head_user])
            else:
                summary.set_user(screen_name)


        summary.add_thread(main_thread,
                           cleaned_rest,
                           quotes,
                           tweets)

        # write out user file
        summary.write()



def construct_org_files(combined_threads_dir, org_dir, all_users, source_ids:TweetTodoFile):
    logging.info("Constructing org files from: {} \n\tto: {}".format(combined_threads_dir, org_dir))
    # get all user summary jsons
    user_summaries = [join(combined_threads_dir, x) for x in listdir(combined_threads_dir) if splitext(x)[1] == ".json"]

    for summary in user_summaries:
        org_obj = TwitterOrg(summary,
                             org_dir,
                             source_ids,
                             all_users)
        if not bool(org_obj):
            continue

        org_obj.build_threads()
        org_obj.build_unused()
        org_obj.write()
        org_obj.download_media()