# matterport-dl
A tool to download/archive [Matterport](https://matterport.com) virtual tours.  Supports most matterport virtual tour links ( ie https://my.matterport.com/show/?m=roWLLMMmPL8 ). This project is not in any way associated with or supported by matterport.com in any way. 

See [CHANGELOG.md] for changes and [DEVELOPERS.md] for some developer notes.

It supports offline viewing of virtual tours and most tour features including:
- Walking/browsing the tour using mouse or keyboard
- Virtual reality supported tours
- Measuring items within the tour
- Information nodes and popup data
- Dollhouse and floorplan views (see "Advanced Options" section below)

# Usage

1. Install Python 3.12 or higher.
2. Download the files from this repository (click Code button near upper right and click download zip). 
3. Extract these files to a local folder.
4. At the root of the folder run `pip install -r requirements.txt`
5. Archive a virtual tour by running `matterport-dl.py [url_or_page_id]`, you may need to use `python3 matterport-dl.py ...` or `python matterport-dl.py ...` instead.
6. Revisit an archived virtual tour by running `matterport-dl.py [url_or_page_id] 127.0.0.1 8080` and visiting http://127.0.0.1:8080 in a browser.

## CLI Options
### Download Run Options
- `--base-folder` dir -- folder to store downloaded models in (or serve from) currently: ./downloads
- `--brute-js`  -- downloading the range of matterports many JS files numbered 1->999.js, through trying them all rather than just the ones we know
- `--proxy` 127.0.0.1:8866 -- using web proxy specified for all requests
- `--no-tilde`  -- disables allowing tildes on file paths, likely must be disabled for Apple/Linux, should be enabled during capture run
- `--alias` name -- create an alias symlink for the download with this name, does not override any existing (can be used when serving)
- `--no-advanced-download`  -- disables downloading advanced assets enables things like skyboxes, dollhouse, floorplan layouts
- `--debug`  -- debug mode enables select debug output to console or the debug/ folder mostly for developers
- `--console-log`  -- showing all log messages in the console rather than just the log file, very spammy
### Serving options
- `--base-folder` dir -- folder to store downloaded models in (or serve from) currently: ./downloads
        Any option can have a no prefix added (or removed if already has) to invert the option,  ie `--no-proxy` disables a proxy if one was enabled.  `--no-advanced-download` disables the default enabled advanced download.
	
# Additional Notes
* It is possible to host these Matterport archives using standard web servers however: 1) Certain features beyond the tour itself may not work.  2)  #1 may be fixable by specific rewrite rules for apache/nginx.  These are not currently provided but if you look at `OurSimpleHTTPRequestHandler` class near the bottom of the source file you can likely figure out what redirects we do.

* As improvements are made to the script you can often upgrade old archives but simply running the script again.  Any existing files downloaded are generally skipped so it will run much faster.  This is not a guarantee so backup your important archives first.

* As matterport changes their code things will likely need to be updated in the script. A good place to start is looking at the server.log file for any lines that say "404 error" in them, these are likely additional files we need to download for the archive to work.  

# [Reddit thread](https://www.reddit.com/r/DataHoarder/comments/nycjj4/release_matterportdl_a_tool_for_archiving/)
