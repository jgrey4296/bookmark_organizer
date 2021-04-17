"""
Automate twitter archiving

"""
# https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html
from typing import List, Set, Dict, Tuple, Optional, Any
from typing import Callable, Iterator, Union, Match
from typing import Mapping, MutableMapping, Sequence, Iterable
from typing import cast, ClassVar, TypeVar, Generic

import sys
import datetime
from os import listdir, mkdir
from os.path import join, isfile, exists, abspath
from os.path import split, isdir, splitext, expanduser
from shutil import copyfile, rmtree
import argparse
import configparser
import json
import logging as root_logger
import re
import uuid

import requests
import networkx as nx
import twitter

USER_FILE_TEMPLATE = "user_{}.json"
PERMALINK_RE = re.compile(r"\[.+?/status/(\d+)\]\]")
DATE_RE = r"%a %b %d %H:%M:%S +0000 %Y"
GROUP_AMNT = 100
DEFAULT_CONFIG = "secrets.config"
DEFAULT_TARGET = ".temp_download"

def parse_date(a_str):
    """ Parse a twitter 'created_at' string to a date """
    return datetime.datetime.strptime(a_str, DATE_RE)

def retarget_url(url, new_target_dir):
    logging.debug("Retargeting URL: {} to {}".format(split(url)[1], new_target_dir))
    return join(new_target_dir, split(url)[1])

def download_media(media_dir, media):
    """ Download all media mentioned in json files """
    logging.info("Downloading media {} to: {}".format(len(media), media_dir))

    scaler = int(len(media) / 100) + 1
    for i, x in enumerate(media):
        if i % scaler == 0:
            logging.info("{}/100".format(int(i/scaler)))

        filename = split(x)[1]
        if exists(join(media_dir, filename)):
            continue

        try:
            request = requests.get(x)
            with open(join(media_dir, filename), 'wb') as f:
                f.write(request.content)
        except Exception as e:
            logging.warning("Error Downloading: {}".format(x))
            logging.warning(str(e))


def download_tweets(twit, json_dir, target_ids, lib_ids=None):
    """ Download all tweets and related tweets for a list """
    logging.info("Downloading tweets to: {}".format(json_dir))
    logging.info("Reading existing tweet jsons")
    json_files = [join(json_dir, x) for x in listdir(json_dir) if splitext(x)[1] == ".json"]
    json_ids = set()
    for jfile in json_files:
        json_ids.update(extract_tweet_ids_from_json(jfile))

    logging.info("Found {} existing tweet ids in jsons".format(len(json_ids)))
    # remove tweet id's already in library
    logging.info("Removing existing tweets from queue")
    if lib_ids is None:
        lib_ids = set()
    remaining = (target_ids - lib_ids) - json_ids
    logging.info("Remaining ids to process: {}".format(len(remaining)))

    if not bool(remaining):
        return True

    queue = list(remaining)
    # Loop:
    while bool(queue):
        logging.info("Queue loop: {}".format(len(queue)))
        # Pop group amount:
        current = set(queue[:GROUP_AMNT])
        current -= json_ids
        current = list(current)
        queue = queue[GROUP_AMNT:]

        try:
            ## download tweets
            results = twit.GetStatuses(current, trim_user=True)

            # add results to results dir
            new_json_file = join(json_dir, "{}.json".format(uuid.uuid1()))
            assert(not exists(new_json_file))
            with open(new_json_file, 'w') as f:
                as_json = "[{}]".format(",".join([json.dumps(x._json) for x in results]))
                f.write(as_json)

            # update ids
            json_ids.update([x.id_str for x in results])

            # Add new referenced ids:
            for x in results:
                if 'in_reply_to_status_id_str' in x._json and x._json['in_reply_to_status_id_str'] is not None:
                    queue.append(str(x._json['in_reply_to_status_id_str']))
                if 'quoted_status_id_str' in x._json and x._json['quoted_status_id_str'] is not None:
                    queue.append(x._json['quoted_status_id_str'])

        except Exception as e:
            # handle failure
            breakpoint()
            logging.warning("Exception")

    return False

def assemble_threads(json_dir):
    """ Create a graph of tweet replies and quotes """
    logging.info("Assembling threads graph from: {}".format(json_dir))
    json_files = [join(json_dir, x) for x in listdir(json_dir) if splitext(x)[1] == ".json"]
    di_graph = nx.DiGraph()
    for jfile in json_files:
        # load in each json,
        with open(jfile, 'r') as f:
            data = json.load(f, strict=False)

        # construct connection graph
        for entry in data:
            # get tweet id, reply_id, quote_id
            tweet_id = entry['id_str']
            di_graph.add_node(tweet_id, source_file=jfile)

            if 'in_reply_to_status_id_str' in entry and entry['in_reply_to_status_id_str']:
                # link tweets
                di_graph.add_edge(tweet_id,
                                  str(entry['in_reply_to_status_id_str']),
                                  type="reply")

            if 'quoted_status_id_str' in entry and entry['quoted_status_id_str']:
                di_graph.add_edge(tweet_id,
                                  str(entry['quoted_status_id_str']),
                                  type="quote")

    return di_graph

def create_component_files(components, tweet_dir, component_dir, di_graph, twit=None):
    """ Create intermediate component files of tweet threads """
    logging.info("Creating {} component files\n\tfrom: {}\n\tto: {}".format(len(components), tweet_dir, component_dir))
    id_map = {}
    for comp_set in components:
        # Then to each id in that component:
        component_filename = join(component_dir, "component_{}.json".format(uuid.uuid1()))
        assert(not exists(component_filename))
        for x in comp_set:
            if x not in id_map:
                id_map[x] = []
            id_map[x].append(component_filename)


    # create separate component files
    logging.info("Copying to component files")
    missing_ids = set()
    json_files = [join(tweet_dir, x) for x in listdir(tweet_dir) if splitext(x)[1] == ".json"]
    for jfile in json_files:
        with open(jfile, 'r') as f:
            data = json.load(f, strict=False)

        for tweet in data:
            # Add tweet to any of its components
            id_str = tweet['id_str']
            if id_str not in id_map:
                missing_ids.add(id_str)
                continue

            component_filenames = set(id_map[id_str])
            for comp_f_name in component_filenames:
                new_file = not exists(comp_f_name)
                with open(comp_f_name, 'a') as f:
                    if new_file:
                        f.write("[")
                    else:
                        f.write(",")
                    f.write(json.dumps(tweet))

            # Add tweet to any component that quotes it
            quoter_edges = [x for x in di_graph[id_str] if di_graph[id_str][x] == "quote"]
            discovered = set()
            while bool(quoter_edges):
                quoter_id = quoter_edges.pop(0)
                discovered.add(quoter_id)
                additional_quotes = [x for x in di_graph[quoter_id] if di_graph[quoter_id][x] == "quote"]
                quoter_edges += [x not in discovered for x in additional_quotes]


                component_filenames = set(id_map[quoter_id])
                for comp_f_name in component_filenames:
                    new_file = not exists(comp_f_name)
                    with open(comp_f_name, 'a') as f:
                        if new_file:
                            f.write("[")
                        else:
                            f.write(",")
                        f.write(json.dumps(tweet))

    if bool(missing_ids):
        logging.info("Missing: {}".format(missing_ids))
        if not download_tweets(twit, tweet_dir, missing_ids):
            exit()


    # After every file is finished, add a final ]
    for x in [join(component_dir, x) for x in listdir(component_dir) if splitext(x)[1] == ".json"]:
        with open(x, 'a') as f:
            f.write(']')

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
        tweets = {x['id_str'] : x for x in data}
        user_counts = {t['user']['id_str'] : 0 for t in data}
        for x in data:
            user_counts[x['user']['id_str']] += 1


        head_user = max(user_counts.items(), key=lambda x: x[1])[0]
        screen_name = str(head_user)
        if head_user in user_lookup:
            screen_name = user_lookup[head_user]['screen_name']

        graph = nx.DiGraph()
        [graph.add_edge(str(x['in_reply_to_status_id_str']), x['id_str']) for x in data
         if x['in_reply_to_status_id_str'] is not None]

        quotes = [x['quoted_status_id_str'] for x in data if 'quoted_status_id_str' in x and x['quoted_status_id_str']]
        roots = [x['id_str'] for x in data if x['in_reply_to_status_id_str'] is None and x['id_str'] not in quotes]
        # dfs to get longest chain

        chains = []

        if bool(roots):
            chains = dfs_chains(graph, roots)

        if not bool(chains):
            chains = [roots] + [quotes]

        # Assign main thread
        main_thread = max(chains, key=lambda x: len(x))
        main_set = set(main_thread)
        main_index = chains.index(main_thread)
        # assign secondary conversations
        rest = chains[:main_index] + chains[main_index+1:]

        rest = [x for x in rest if bool(x)]
        cleaned_rest = []
        for thread in rest:
            cleaned = [x for x in thread if x not in main_set]
            cleaned_rest.append(cleaned)
            main_set.update(cleaned)

        # create user file if not exist
        user_file = join(combined_threads_dir, USER_FILE_TEMPLATE.format(screen_name))
        user_data = {}
        if exists(user_file):
            with open(user_file, 'r') as f:
                user_data = json.load(f, strict=False)

        if 'user' not in user_data:
            if head_user in user_lookup:
                user_data['user'] = user_lookup[head_user]
            else:
                user_data['user'] = {'screen_name': screen_name}
            user_data['threads'] = []
            user_data['tweets'] = {}

        user_data['threads'].append({'main_thread' : main_thread,
                                     'rest' : cleaned_rest,
                                     'quotes' : quotes})

        user_data['tweets'].update(tweets)


        # write out user file
        with open(user_file, 'w') as f:
            json.dump(user_data, f)

def construct_org_files(combined_threads_dir, org_dir, all_users, media_dir):
    logging.info("Constructing org files from: {} \n\tto: {}".format(combined_threads_dir, org_dir))
    # get all user summary jsons
    user_summaries = [join(combined_threads_dir, x) for x in listdir(combined_threads_dir) if splitext(x)[1] == ".json"]

    for summary in user_summaries:
        with open(summary, 'r') as f:
            data = json.load(f, strict=False)

        tweets = data['tweets']
        out_file  = join(org_dir, "{}.org".format(data['user']['screen_name']))
        out_files_dir = join(org_dir, "{}_files".format(data['user']['screen_name']))

        media = set()
        output = []

        # Add initial line
        output.append("* {}'s Threads".format(data['user']['screen_name']))
        output.append("\t:PROPERTIES:")
        if 'name' in data['user']:
            output.append("\t:NAME: {}".format(data['user']['name']))
        if 'followers_count' in data['user']:
            output.append("\t:FOLLOWERS: {}".format(data['user']['followers_count']))
        if 'description' in data['user']:
            output.append("\t:DESCRIPTION: {}".format(data['user']['description']))
        if 'location' in data['user']:
            output.append("\t:LOCATION: {}".format(data['user']['location']))
        if 'url' in data['user']:
            output.append("\t:URL: [[{}]]".format(data['user']['url']))
        output.append("\t:END:")

        # add conversations
        for thread in data['threads']:
            thread_out, thread_media = thread_to_strings(thread, out_files_dir, all_users, tweets)
            output += thread_out
            media.update(thread_media)


        with open(out_file, 'w') as f:
            f.write("\n".join(output))

        # copy media to correct output files dir
        if not exists(out_files_dir):
            mkdir(out_files_dir)

        for x in media:
            retargetted = retarget_url(x, media_dir)
            copy_to = retarget_url(x, out_files_dir)
            copyfile(retargetted, copy_to)

def thread_to_strings(thread, redirect_url, all_users, tweets):
    logging.info("Creating thread")
    assert(isinstance(thread, dict))
    assert(isinstance(all_users, dict))
    links = set()
    media = set()
    used_tweets = set()
    output = []
    main_thread = [tweets[x] for x in thread['main_thread'] if x in tweets]
    if not bool(main_thread):
        return output, media

    quotes = thread['quotes']
    # Add user info
    # append tweets in order as a thread
    date = parse_date(main_thread[0]['created_at'])

    # TODO: format this
    output.append("** Thread: {}".format(date))
    output.append("*** Main Thread")
    # add tweets of main thread
    used_tweets.update([x['id_str'] for x in main_thread])
    for x in main_thread:
        mresult, mmedia, mlinks = tweet_to_string(x, all_users, redirect_url)
        output.append(mresult)
        media.update(mmedia)
        links.update(mlinks)


    output.append("*** Conversations")
    for conv in thread['rest']:
        if not bool(conv):
            continue
        missing_tweets = [x for x in conv if x not in tweets]
        conv_tweets = [tweets[x] for x in conv if x in tweets]
        if not bool(conv_tweets):
            logging.info("Empty Conversation: {}".format(conv))
            continue
        # TODO get links and media
        conv_links = []
        conv_media = []

        screen_name = conv_tweets[0]['user']['id_str']
        if screen_name in all_users:
            screen_name = all_users[screen_name]['screen_name']
        output.append("**** Conversation: {}".format(screen_name))

        # Add tweets
        new_tweets = [x['id_str'] for x in conv_tweets]
        used_tweets.update(new_tweets)
        for x in conv_tweets:
            mresult, mmedia, mlinks = tweet_to_string(x, all_users, redirect_url, level=5)
            output.append(mresult)
            media.update(mmedia)
            links.update(mlinks)

        if bool(missing_tweets):
            output.append("***** MISSING")
            output += [x for x in missing_tweets]

    output.append("*** Links")
    output += ["[[{}]]".format(x) for x in links]
    output.append("")

    output.append("*** Media")
    output += ["[[{}][{}]]".format(retarget_url(x, redirect_url), split(x)[1]) for x in media]

    output.append("")
    return output, media

def tweet_to_string(tweet, all_users, url_prefix, level=4):
    output = []

    indent = "*" * level
    screen_name = "Unknown"
    try:
        screen_name = all_users[tweet['user']['id_str']]['screen_name']
    except KeyError as e:
        logging.warning("Unknown Screen name: {}".format(tweet['user']['id_str']))

    try:
        hashtags = [x['text'] for x in tweet['entities']['hashtags']]
    except KeyError as e:
        breakpoint()

    hash_str = ""
    if bool(hashtags):
        hash_str = ":{}:".format(":".join(hashtags))
    output.append("{} @{}          {}".format(indent, screen_name, hash_str))

    # Add Details drawer
    output.append("\t:PROPERTIES:")
    output.append("\t:PERMALINK: [[https://twitter.com/{}/status/{}][/{}/{}]]".format(screen_name,
                                                                                      tweet['id_str'],
                                                                                      screen_name,
                                                                                      tweet['id_str']))
    if tweet["in_reply_to_status_id_str"] is not None:
        output.append("\t:REPLY_TO: [[https://twitter.com/{}/status/{}][/{}/{}]]".format(tweet['in_reply_to_screen_name'],
                                                                                         str(tweet['in_reply_to_status_id_str']),
                                                                                         tweet['in_reply_to_screen_name'],
                                                                                         str(tweet['in_reply_to_status_id_str'])))

    if "quoted_status_id_str" in tweet:
        quote_name = tweet['quoted_status_id_str']
        if quote_name in all_users:
            quote_name = all_users[tweet['quoted_status_id_str']]['screen_name']

        output.append("\t:QUOTE: [[https://twitter.com/{}/status/{}][/{}/{}]]".format(quote_name,
                                                                                      tweet['quoted_status_id_str'],
                                                                                      quote_name,
                                                                                      tweet['quoted_status_id_str']))
    # in reply to
    if 'favorite_count' in tweet:
        output.append("\t:FAVORITE_COUNT: {}".format(tweet['favorite_count']))
    if 'retweet_count' in tweet:
        output.append("\t:RETWEET_COUNT: {}".format(tweet['retweet_count']))

    output.append("\t:DATE: {}".format(parse_date(tweet['created_at'])))
    output.append("\t:END:")

    # add tweet contents
    output.append(tweet['full_text'])


    # quoted_status -> quote -> tweet
    qlinks = []
    qmedia = []
    if "quoted_status" in tweet:
        output.append("")
        quote_level = level + 1
        qresult, qmedia, qlinks = tweet_to_string(tweet['quoted_status'], all_users, url_prefix, level=quote_level)
        output.append(qresult)


    # add tweet urls
    output.append("")
    links = [x['expanded_url'] for x in tweet['entities']['urls']]
    output += ["[[{}]]".format(x) for x in links]

    # add tweet media
    media = []
    if 'media' in tweet:
        output.append("")

        media += ([m['media_url'] for m in tweet['entities']['media']])
        videos = [m['video_info'] for m in tweet['entities']['media'] if m['type'] == "video"]

        urls = [n['url'] for m in videos for n in m['variants'] if n['content_type'] == "video/mp4"]
        media += [x.split("?")[0] for x in urls]

        output += ["[[{}][{}]]".format(retarget_url(x, url_prefix), split(x)[1]) for x in media]


    output.append("")
    return "\n".join(output), media + qmedia, links + qlinks


def extract_tweet_ids_from_file(the_file, simple=False):
    """ Get all mentioned tweets in a file.
    Can search for regexs, or treat file as a line list of urls """
    use_regex = PERMALINK_RE
    if simple:
        use_regex = re.compile(r"/status/(\d+)")

    exists(the_file)
    with open(the_file, 'r') as f:
        lines = f.readlines()

    # grep file lines for permalinks
    results = set()
    for line in lines:
        match = use_regex.search(line)
        if match is not None:
            results.add(match[1])

    return results

def extract_tweet_ids_from_json(the_file):
    """ Get all tweet ids from a json file """
    try:
        with open(the_file, 'r') as f:
            data = json.load(f, strict=False)
    except Exception as e:
        logging.info("File issue: {}".format(the_file))
        raise e

    ids = [x['id_str'] for x in data]
    return ids

def extract_media_and_users_from_json(the_file):
    """ Get all media urls and user ids from json file """
    try:
        with open(the_file, 'r') as f:
            data = json.load(f, strict=False)
    except Exception as e:
        logging.info("File issue: {}".format(the_file))
        raise e

    ids = set()
    media = set()
    media_variants = []
    for x in data:
        if 'entities' in x and 'media' in x['entities']:
            entities = x['entities']
            media.update([m['media_url'] for m in entities['media']])

            videos = [m['video_info'] for m in entities['media'] if m['type'] == "video"]
            for video in videos:
                urls = [n['url'] for n in video['variants'] if n['content_type'] == "video/mp4"]
                trimmed = [x.split("?")[0] for x in urls]
                media.update(trimmed)
                media_variants.append(trimmed)

        if 'extended_entities' in x and 'media' in x['extended_entities']:
            entities = x['extended_entities']
            media.update([m['media_url'] for m in entities['media']])

            videos = [m['video_info'] for m in entities['media'] if m['type'] == "video"]
            for video in videos:
                urls = [n['url'] for n in video['variants'] if n['content_type'] == "video/mp4"]
                trimmed = [x.split("?")[0] for x in urls]
                media.update(trimmed)
                media_variants.append(trimmed)

        if 'in_reply_to_user_id_str' in x:
            ids.add(str(x['in_reply_to_user_id_str']))

        if "quoted_status" in x:
            ids.add(x['quoted_status']['user']['id_str'])

        ids.add(x['user']['id_str'])


    return ids, media, media_variants


def get_all_tweet_ids(*the_dirs) -> Set[Any]:
    """ For a list of directories, dfs the directory to get all files,
    and get all mentioned tweets in those files """
    tweet_ids = set()

    for a_dir in the_dirs:
        if isfile(a_dir):
            with open(a_dir, 'r') as f:
                tweet_ids.update([x.strip() for x in f.readlines()])

        elif isdir(a_dir):
            all_files = dfs_directory(*the_dirs)
            for x in all_files:
                tweet_ids.update(extract_tweet_ids_from_file(x))

    return tweet_ids

def get_user_identities(users_file, twit, users):
    """ Get all user identities from twitter """
    logging.info("Getting user identities")
    total_users = {}
    user_queue  = list(users)
    if exists(users_file):
        with open(users_file,'r') as f:
            total_users.update({x['id_str'] : x for x in  json.load(f, strict=False)})

        users -= total_users.keys()
        logging.info("Already retrieved {}, {} remaining".format(len(total_users), len(users)))
        user_queue = list(users)

    while bool(user_queue):
        current = user_queue[:100]
        user_queue = user_queue[100:]

        try:
            data = twit.UsersLookup(user_id=current)
            logging.info("Retrieved: {}".format(len(data)))
            new_users = [json.loads(x.AsJsonString()) for x in data]
            total_users.update({x['id_str'] : x for x in new_users})

        except twitter.error.TwitterError as err:
            logging.info("Does not exist: {}".format(current))


    with open(users_file, 'w') as f:
        json.dump(list(total_users.values()), f)

    return total_users

def get_user_and_media_sets(json_dir):
    """ Get all user ids and media urls """
    logging.info("Getting media urls")
    json_files = [join(json_dir, x) for x in listdir(json_dir) if splitext(x)[1] == ".json"]
    users = set()
    media = set()
    variants = []
    for f in json_files:
        tusers, tmedia, tvariants = extract_media_and_users_from_json(f)
        users.update(tusers)
        media.update(tmedia)
        variants += tvariants

    logging.info("Found {} unique media files".format(len(media)))
    logging.info("Found {} unique users".format(len(users)))

    return users, media, variants


def dfs_edge(graph, edge):
    """ Getting non-quote tweets """
    found = set()
    queue = [edge]

    while bool(queue):
        current = queue.pop(0)
        l, r = current
        if l in found and r in found:
            continue

        found.add(l)
        found.add(r)
        to_add = [(l, x) for x in graph.adj[l] if graph.adj[l][x]['type'] == "reply"]
        to_add += [(r, x) for x in graph.adj[r] if graph.adj[r][x]['type'] == "reply"]

        if len(to_add) > 100:
            breakpoint()
        queue += to_add

    return found

def dfs_for_components(di_graph):
    """ DFS a graph for all connected components """
    # Convert to undirected graph
    graph = nx.Graph(di_graph)

    # DFS for components
    components = []
    edge_set = set(graph.edges)
    discovered = set()
    logging.info("DFS on Components: {}".format(len(edge_set)))
    count = 0
    log_on_count = len(edge_set) * 0.1
    while bool(edge_set):
        count += 1
        current = edge_set.pop()
        l, r = current
        if l in discovered and r in discovered:
            continue
        # Get connected edges (direct replies only, not quotes)
        connected_ids = dfs_edge(graph, current)
        # Then get quotes
        quotes = [y for x in connected_ids for y in graph.adj[x] if graph.adj[x][y]['type'] == 'quote']
        while bool(quotes):
            current = quotes.pop()
            connected_ids.add(current)
            quotes += [y for y in graph.adj[current]
                       if graph.adj[current][y]['type'] == 'quote' and y not in connected_ids]

        components.append(connected_ids)
        discovered.update(connected_ids)
        if count > log_on_count:
            count = 0
            logging.info("Edge Set Size: {}".format(len(edge_set)))

    logging.info("Found {} components".format(len(components)))
    return components

def dfs_directory(*dirs, filetype=".org"):
    """ DFS a directory for a filetype """
    found = []
    queue = [] + list(dirs)

    while bool(queue):
        current = queue.pop(0)
        # Add files
        if isfile(current):
            found.append(current)
        else:
            found += [join(current, x) for x in listdir(current)
                      if isfile(join(current, x)) and splitext(x)[1] == filetype]
            # Continue for directories
            queue += [join(current, x) for x in listdir(current)
                      if isdir(join(current, x)) and x != ".git"]

    return found

def dfs_chains(graph, roots):
    results = []
    queue = [[x] for x in roots]
    discovered = set()
    while bool(queue):
        path = queue.pop()
        discovered.update(path)
        if path[-1] not in graph:
            results.append(path)
            continue
        edges = [x for x in graph[path[-1]].keys() if x not in discovered]
        if not bool(edges):
            results.append(path)
        else:
            queue += [path + [x] for x in edges]

    return results


def main():

    ####################
    # Setup argparser
    #see https://docs.python.org/3/howto/argparse.html
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="\n".join([""]))
    parser.add_argument('--config', default=DEFAULT_CONFIG, help="The Secrets file to access twitter")
    parser.add_argument('--target', default=DEFAULT_TARGET, help="The target dir to process/download to")
    parser.add_argument('--library', action="append",       help="Location of already downloaded tweets")
    parser.add_argument('--export',  help="File to export all library tweet ids to, optional")
    parser.add_argument('--tweet', help="A Specific Tweet URL to handle, for CLI usage/ emacs use")

    args = parser.parse_args()
    args.config = abspath(expanduser(args.config))
    if args.library is not None:
        args.library = [abspath(expanduser(x)) for x in args.library]
    else:
        args.library = []

    if args.export is not None:
        args.export = abspath(expanduser(args.export))

    # Auto setup
    target_dir = abspath(expanduser(args.target))
    target_file = join(target_dir, "bookmarks.txt")
    org_dir = join(target_dir, "orgs")
    tweet_dir = join(target_dir, "tweets")
    combined_threads_dir = join(target_dir, "threads")
    component_dir = join(target_dir, "components")
    media_dir = join(target_dir, "media")
    library_ids = join(target_dir, "all_ids")
    users_file = join(target_dir, "users.json")

    if exists(library_ids):
        args.library.append(library_ids)

    if args.tweet is not None and args.target == DEFAULT_TARGET and exists(DEFAULT_TARGET):
        rmtree(DEFAULT_TARGET)

    missing_dirs = [x for x in [target_dir,
                                tweet_dir,
                                org_dir,
                                combined_threads_dir,
                                component_dir,
                                media_dir] if not exists(x)]

    for x in missing_dirs:
        logging.info("Creating {} Directory".format(x))
        mkdir(x)


    logging.info("Target Dir: {}".format(target_dir))
    logging.info("Library: {}".format(args.library))
    logging.info("Config: {}".format(args.config))
    ####################
    # Read Configs
    config = configparser.ConfigParser()
    with open(args.config, 'r') as f:
        config.read_file(f)

    ####################
    # INIT twitter object
    logging.info("---------- Initialising Twitter")
    twit = twitter.Api(consumer_key=config['DEFAULT']['consumerKey'],
                       consumer_secret=config['DEFAULT']['consumerSecret'],
                       access_token_key=config['DEFAULT']['accessToken'],
                       access_token_secret=config['DEFAULT']['accessSecret'],
                       sleep_on_rate_limit=config['DEFAULT']['sleep'],
                       tweet_mode='extended')

    # Extract all tweet id's from library
    library_tweet_ids = set()
    if args.tweet is None:
        logging.info("---------- Getting Library Tweet Details")
        library_tweet_ids = get_all_tweet_ids(*args.library)
        logging.info("Found {} library tweets".format(len(library_tweet_ids)))

    if args.tweet is not None and args.export is not None:
        logging.info("---------- Exporting to: {}".format(args.export))
        with open(args.export, 'w') as f:
            f.write("\n".join(library_tweet_ids))
            sys.exit()

    # read file of tweet id's
    logging.info("---------- Getting Target Tweet ids")
    if args.tweet is None:
        source_ids = set(extract_tweet_ids_from_file(target_file, simple=True))
    else:
        source_ids = set([split(args.tweet)[1]])
        logging.info("Specific Tweet: {}".format(source_ids))
    logging.info("Found {} source ids".format(len(source_ids)))

    # Download tweets
    download_tweets(twit, tweet_dir, source_ids, lib_ids=library_tweet_ids)

    user_set, media_set, variant_list = get_user_and_media_sets(tweet_dir)

    # write out video variant/duplicates
    with open(join(target_dir, "video_variants.json"), "w") as f:
        f.write(json.dumps(variant_list))

    # download media
    download_media(media_dir, media_set)
    # Get user identities
    all_users = get_user_identities(users_file, twit, user_set)

    # --------------------
    logging.info("-------------------- Finished Retrieval")

    # Now create threads
    logging.info("---------- Assembling Threads")
    di_graph = assemble_threads(tweet_dir)

    logging.info("---------- Creating Components")
    components = dfs_for_components(di_graph)
    create_component_files(components, tweet_dir, component_dir, di_graph, twit=twit)

    logging.info("---------- Creating user summaries")
    construct_user_summaries(component_dir, combined_threads_dir, all_users)
    logging.info("---------- Constructing org files")
    construct_org_files(combined_threads_dir, org_dir, all_users, media_dir)


if __name__ == "__main__":
    # Setup root_logger:
    LOGLEVEL = root_logger.DEBUG
    LOG_FILE_NAME = "log.{}".format(splitext(split(__file__)[1])[0])
    root_logger.basicConfig(filename=LOG_FILE_NAME, level=LOGLEVEL, filemode='w')

    console = root_logger.StreamHandler()
    console.setLevel(root_logger.INFO)
    root_logger.getLogger('').addHandler(console)
    logging = root_logger.getLogger(__name__)
    logging.info("Automated Twitter Archiver")

    main()
