# matterport-dl
A tool to download/archive [Matterport](https://matterport.com) virtual tours.  Supports most matterport virtual tour links ( ie https://my.matterport.com/show/?m=roWLLMMmPL8 ). This project is not in any way associated with or supported by matterport.com in any way. It supports offline viewing of virtual tours and most tour features including: Walking/browsing the tour using mouse or keyboard.  Virtual reality supported tours.   Measuring items within the tour.  Information nodes and popup data.  Dollhouse* and floorplan* views (see "Advanced Options" section below).

## Requirements

- Python 3.6+
- Pipenv

## Usage

1. `git clone https://github.com/rebane2001/matterport-dl`
1. `pipenv install`
1. `pipenv shell`
1. `python matterport-dl.py URL_OR_PAGE_ID` (archiving)
1. `python matterport-dl.py URL_OR_PAGE_ID 127.0.0.1 8080` (replaying archived content)

## Advanced Options
- `--proxy 127.0.0.1:3128` to use the specified proxy
- `--advanced-download` to download the needed files to support dollhouse/floorplan views
  NOTE: Must use built in webserver to host content for this to work.


## Additional Notes

* It is possible to host these Matterport archives using standard web servers however:
  1. Certain features beyond the tour itself may not work.
  1. The previous item may be fixable by specific rewrite rules for Apache Httpd / NGINX. These are not currently provided but if you look at `OurSimpleHTTPRequestHandler` class near the bottom of the source file you can likely figure out what redirects we do.
* As improvements are made to the script you can often upgrade old archives but simply running the script again.  Any existing files downloaded are generally skipped so it will run much faster.  This is not a guarantee so backup your important archives first.
* As matterport changes their code things will likely need to be updated in the script. A good place to start is looking at the server.log file for any lines that say "404 error" in them, these are likely additional files we need to download for the archive to work.  

# [Reddit thread](https://www.reddit.com/r/DataHoarder/comments/nycjj4/release_matterportdl_a_tool_for_archiving/)
