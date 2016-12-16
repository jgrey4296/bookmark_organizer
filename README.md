# Bookmark organiser

To deal with the unmanageable morass of bookmarks I collect 
Safari, Firefox, and Chrome export html bookmarks in the [Netscape bookmark
file format](https://msdn.microsoft.com/en-us/library/aa753582(v=vs.85).aspx).

This program loads those in, **ignoring** groups but **preserving** tags,
stores them in a trie based on the bookmarks url path, removes duplicates,
then collapses trie paths that have only a single child. This collapsed trie
is then exported out as the file 'simplified_bookmarks.html' for reloading 
into Firefox/Chrome/Safari

## Usage

Create the directory ./raw_bookmarks, and fill it with the html files exported from your browsers.

run *python main.py* 

Reload the simplified bookmarks back into your browser. 
