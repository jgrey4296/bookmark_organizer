# Setup root_logger:
import logging as root_logger
LOGLEVEL = root_logger.DEBUG
logFileName = "bkmk_network.log"
root_logger.basicConfig(filename=logFileName, level=LOGLEVEL, filemode='w')

console = root_logger.StreamHandler()
console.setLevel(root_logger.INFO)
root_logger.getLogger('').addHandler(console)
logging = root_logger.getLogger(__name__)
##############################
import IPython
import networkx as nx
from bookmark_organiser.bkmkorg import html_opener
from os.path import join,isfile,exists,isdir
from os import listdir

FOCUS_FILE = 'tor_bookmarks.html'

if not isfile(FOCUS_FILE):
    logging.exception("File does not exist");
    exit()

bookmarks = html_opener.open_and_extract_bookmarks(FOCUS_FILE)

#Now loaded, so convert to a graph:
bkmkGraph = nx.Graph()
try:
    for i,bkmk in enumerate(bookmarks):
        if i % 100 == 0:
            logging.info("Processing bkmk {}".format(i))
        bkmkGraph.add_node("{}_bkmk".format(bkmk.name),type='bkmk',name=bkmk.name, url=bkmk.url)
        for tag in bkmk.tags:
            if not bkmkGraph.has_node(tag):
                bkmkGraph.add_node(tag,type='tag')
                bkmkGraph.add_edge("{}_bkmk".format(bkmk.name),tag,type='bkmk_tag_e')
                for tag_2 in bkmk.tags:
                    if tag == tag_2:
                        continue
                    if bkmkGraph.has_edge(tag,tag_2):
                        bkmkGraph.edge[tag][tag_2]['count'] += 1
                        continue
                    if not bkmkGraph.has_node(tag_2):
                        bkmkGraph.add_node(tag_2,type='tag')
                        bkmkGraph.add_edge(tag,tag_2,type='tag_tag_e',count=1)
except Exception as e:
    IPython.embed(simple_prompt=True)
else:
    IPython.embed(simple_prompt=True)
    