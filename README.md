# matterport-dl
A tool to download/archive [Matterport](https://matterport.com) virtual tours.  Supports most matterport virtual tour links ( ie https://my.matterport.com/show/?m=roWLLMMmPL8 ). This project is not in any way associated with or supported by matterport.com in any way. It supports offline viewing of virtual tours and most tour features including: Walking/browsing the tour using mouse or keyboard.  Virtual reality supported tours.   Measuring items within the tour.  Information nodes and popup data.  Dollhouse* and floorplan* views (see "Advanced Options" section below).


# Usage

1. Install Python 3.6 or higher.
2. Download the files from this repository (click Code button near upper right and click download zip). 
3. Extract these files to a local folder.
4. Archive a virtual tour by running `matterport-dl.py [url_or_page_id]`, you may need to use `python3 matterport-dl.py ...` or `python matterport-dl.py ...` instead.
5. Revisit an archived virtual tour by running `matterport-dl.py [url_or_page_id] 127.0.0.1 8080` and visiting http://127.0.0.1:8080 in a browser.

# Advanced Options
-   Add `--proxy 127.0.0.1:1234` to a download run to use a proxy for requests
-   Add `--advanced-download` to a download run to try and download the needed textures and files for supporting dollhouse/floorplan views.  NOTE: Must use built in webserver to host content for this to work.

# Docker
## Docker params
```
docker build -t matterport-dl .
docker run -v $(pwd)/clones:/matterport-dl/clones -e M_ID=[url_or_page_id] matterport-dl
docker run -p 8080:8080 -v $(pwd)/clones:/matterport-dl/clones -e M_ID=[url_or_page_id] -e BIND_IP=0.0.0.0 -e BIND_PORT=8080 -e ADV_DL=true -e PROXY=127.0.0.1:1234 -e BASE_FOLDER="./clones" matterport-dl
```

* M_ID Matterport ID or URL
* BIND_PORT Defaults to 8080 if not set
* BIND_IP IP address to bind to. Use `0.0.0.0` unless setting docker network to host.
* ADV_DL is for the --advanced-download flag, and is off by default. Setting this to anything will activate it.
* PROXY is for the --proxy flag, and is off by default.
* BASE_FOLDER is where the downloads go. Defaults to "./clones"

## Docker example
```
docker build -t matterport-dl .
docker run -v $(pwd)/clones:/matterport-dl/clones -e M_ID="https://my.matterport.com/show/?m=roWLLMMmPL8" -e ADV_DL=true matterport-dl
docker run -p 8080:8080 -v $(pwd)/clones:/matterport-dl/clones -e M_ID=roWLLMMmPL8 -e BIND_IP=0.0.0.0 -d matterport-dl
```

## Docker debugging
```
docker build --no-cache -t matterport-dl .
docker run -t -i -p 8080:8080 -v $(pwd)/clones:/matterport-dl/clones -e M_ID=roWLLMMmPL8 -e BIND_IP=0.0.0.0 matterport-dl /bin/bash
```

# Additional Notes
* It is possible to host these Matterport archives using standard web servers however: 1) Certain features beyond the tour itself may not work.  2)  #1 may be fixable by specific rewrite rules for apache/nginx.  These are not currently provided but if you look at `OurSimpleHTTPRequestHandler` class near the bottom of the source file you can likely figure out what redirects we do.

* As improvements are made to the script you can often upgrade old archives but simply running the script again.  Any existing files downloaded are generally skipped so it will run much faster.  This is not a guarantee so backup your important archives first.

* As matterport changes their code things will likely need to be updated in the script. A good place to start is looking at the server.log file for any lines that say "404 error" in them, these are likely additional files we need to download for the archive to work.  

# [Reddit thread](https://www.reddit.com/r/DataHoarder/comments/nycjj4/release_matterportdl_a_tool_for_archiving/)
