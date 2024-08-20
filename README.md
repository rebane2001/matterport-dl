# matterport-dl
A tool to download/archive [Matterport](https://matterport.com) digital twin virtual tours.  Supports most matterport virtual tour links ( ie https://my.matterport.com/show/?m=roWLLMMmPL8 ). This project is not in any way associated with or supported by Matterport Inc in any way all relevant trademarks and rights are reserve Matterport Inc.

See [CHANGELOG.md](CHANGELOG.md) for changes and [DEVELOPERS.md](DEVELOPERS.md) for some developer notes.

It supports offline viewing of virtual tours and most tour features including:
- Walking/browsing the tour using mouse or keyboard
- Virtual reality supported tours
- Measuring items within the tour
- Information nodes and popup data
- Searching rooms
- Dollhouse view
- Floorplan view with room labels and dimensions
- Skyboxes for outside environments
- Most other Matterport plugins

# Usage

1. Install Python 3.12 or higher.
2. Download the files from this repository (click Code button near upper right and click download zip). 
3. Extract these files to a local folder.
4. At the root of the folder run `pip install -r requirements.txt`
5. Archive a virtual tour by running `matterport-dl.py [url_or_page_id]`, you may need to use `python3 matterport-dl.py ...` or `python matterport-dl.py ...` instead.
6. Revisit an archived virtual tour by running `matterport-dl.py [url_or_page_id_or_alias] 127.0.0.1 8080` and visiting http://127.0.0.1:8080 in a browser.

## CLI Options
Any option below can have a no prefix added (or removed if already has) to invert the option,  ie `--no-proxy` disables a proxy if one was enabled.  `--no-advanced-download` disables the default enabled advanced download.

### Download Run Options
- `--base-folder` dir -- folder to store downloaded models in (or serve from) currently: ./downloads
- `--brute-js`  -- downloading the range of matterports many JS files numbered 1->999.js, through trying them all rather than just the ones we know
- `--proxy` 127.0.0.1:8866 -- using web proxy specified for all requests
- `--no-tilde`  -- disables: allowing tildes on file paths, likely must be disabled for Apple/Linux, should be enabled during capture run
- `--alias` name -- create an alias symlink for the download with this name, does not override any existing (can be used when serving)
- `--no-advanced-download`  -- disables: downloading advanced assets enables things like skyboxes, dollhouse, floorplan layouts
- `--debug`  -- debug mode enables select debug output to console or the debug/ folder mostly for developers
- `--console-log`  -- showing all log messages in the console rather than just the log file, very spammy
- `--adv-help`  -- Show advanced command line options normally hidden, not recommended for most users

### Serving Options
- `--base-folder` dir -- folder to store downloaded models in (or serve from) currently: ./downloads
- `--quiet`  -- Only show failure log message items when serving

### Hidden CLI Options
These are more likely to change and/or have bugs. They are generally not for most every day use cases. They are hidden from the CLI help by default and only show up if you pass `--adv-help` as the command line arg.
- `--no-download`  -- disables: Download items (without this it just does post download actions)
- `--no-verify-ssl`  -- disables: SSL verification, mostly useful for proxy situations
- `--no-main-asset-download`  -- disables: Primary asset downloads (normally biggest part of the download)
- `--no-always-download-graph-reqs`  -- disables: Always download/make graphql requests, a good idea as they have important keys
- `--manual-host-replacement`  -- Use old style replacement of matterport URLs rather than the JS proxy, this likely only works if hosted on port 8080 after
- `--auto-serve` "page_id_or_alias|host|port|what-browser" -- This will automatically start the server on 'host' and port 'port' for the download 'page_id_or_alias' the what-browser arg is optional, if specified will also launch the browser once the server starts.  See https://docs.python.org/3/library/webbrowser.html for the different values for the type of browser, for example 'windows-default' or 'firefox'

## Defaults / Config JSON
The tool with automatically load a `defaults.json` file and if given a model attempt to load a `run_args.json` file from the model's download folder as well.  The `run_args.json` file is created automatically whenever a model is downloaded it contains the command line settings that were used at time of download.  This is mostly useful for future runs/serving to make sure the same options are used.  `defaults.json` is loaded (if it exists) from next to the `matterport-dl.py` file.  It is never created by default but can be manually created and can contain any command line option like `run_args.json`.  It is loaded first (if it exists) then `run_args.json` and finally the actual command line args that were passed.  The last specified instance of an arg take presence.  This means if `defaults.json` has `--proxy 127.0.0.1` in it but you pass the `--no-proxy` command line option then the proxy is disabled.

An interesting use case for `defaults.json` can be the `--auto-serve` option as this will automatically start a server (and optionally launch a browser) without any command being passed to matterport-dl.py.  For example if your `defaults.json` contained:
```json
{
	"AUTO_SERVE": "roWLLMMmPL8|127.0.0.1|12345|chrome",
	"QUIET": true
}
```

## Tour Packaging / Single Executable Generation
This script is compatible with the great [Auto PY to EXE](https://github.com/brentvollebregt/auto-py-to-exe). While it mentions "EXE" it is cross platform working on more than just Windows.  It can allow you to create a standalone executable that doesn't require python to run.  A sample configuration that can be imported into Auto PY can be found in the [matterport-exe.json] file.  To Use it run Auto PY click the settings dropdown at the bottom and click "Import Config From JSON File".   You can adjust options also changing most things probably will break something.  This is not tested in one-file mode and now recommended you add a specific digital twin to the additional files in Auto PY.  Click `Convert .py to EXE` and you should get a "output" directory next to `matterport-dl.py`.   Go into the matterport-dl sub folder and you should see your executable.  Assuming you are doing this to host a downloaded model you can create a "downloads" folder next to the `matterport-dl.exe` file (should also have a `package` folder there).  In the downloads folder put the same folder you have in the normal downloads folder from the download.

To have it automatically start serving a specific model when you run the executable you can take advantage of the `defaults.json` file (see the example above).  The defaults file should be created BEFORE you generate the executable and will automatically be bundled in.

## Older Download Compatibility
There is effort put into maintaining compatibility with prior downloaded models however it is possible we may break something by mistake on older models.  Starting with the 2024-08-03 release we now copy the matterport-dl.py and JSNetProxy.js files to the folder with the download itself.  As models are meant to be completely offline hostable one downloaded this should create a point in time known-good copy even if you update matterport-dl.py later to something that breaks.  As we normally only make things better / fix features that don't work these old versions are NOT used by default when you serve up a model.  If your older model has broken and you want to use these you will need to either copy the ones from the download folder over the ones in the root of this repo.

# Additional Notes
* It is possible to host these Matterport archives using standard web servers however: 1) Certain features beyond the tour itself may not work.  2)  #1 may be fixable by specific rewrite rules for apache/nginx.  These are not currently provided but if you look at `OurSimpleHTTPRequestHandler` class near the bottom of the source file you can likely figure out what redirects we do.

* As improvements are made to the script you can often upgrade old archives but simply running the script again.  Any existing files downloaded are generally skipped so it will run much faster.  This is not a guarantee so backup your important archives first.

* As matterport changes their code things will likely need to be updated in the script. A good place to start is looking at the server.log file for any lines that say "404 error" in them, these are likely additional files we need to download for the archive to work.  

# [Reddit thread](https://www.reddit.com/r/DataHoarder/comments/nycjj4/release_matterportdl_a_tool_for_archiving/)
