Not sure we actually need cffi however as performance is better than the native requests lib we use it

previously we used a older style multi-thread concurrency setup.  This has been migrated to async functions but it means any blocking IO we missed can result in large slow downs on the critical functions

If we modify a file we should save the modified version as orig_name.modified.js as long as it ends in .html or .js we will automatically use .modified versions over original.  We want to preserve the original so we can re-run any post processing without redoing the entire download.

Originally a decent amount of work was for externally hosted support, this is somewhat de-prioritized now to making sure the internally served version works

Recently we added a new javascript proxy class [JSNetProxy.js] it allows us to avoid most manual modifications of scripts instead modifying requests at runtime to redirect to our local server.  It is a bit more foolproof to ensuring requests are only go to us.  It also is likely the best way to restore independent hosting outside of the internal engine as it can do things like modify POST requests to get requests.


Some failures are to be expected but a normal run looks something like:
Done, Total potential Request: 76131 Already downloaded Skipped: 20 (0%) Success: 74988 (98%) Failed403: 1119 (1%) Failed404: 24 (0%) FailedUnknown: 0 (0%)

To ensure the proxy script is catching everything (and something isn't just using the hosted url) you can use socat to have a second part direct to the local server:
socat TCP4-LISTEN:9000,fork,reuseaddr TCP4:127.0.0.1:8080

then modify the matterport-dl.py to give the wrong port to JSNetProxy for the redirect

While we can likely enable plguins not originally enabled certain things are not possible if there is not the data.  For example floorplan sq/ft etc only exist if the original model collected the data it requires to compute that.

The CLI arg handling is a bit odd, as everything can have negative forms but sometimes the negative is the default the usage it shows is based on the opposite of the current value.   IE as we default to doing advanced download now there it shows the CLA as `--no-advanced-download` rather than `--advanced-download` and then somehow indicating it is on by default. This becomes a bit confusing if running an existing model.  If a model is passed and it has been run before we try to first load the CLAs that were loaded on the initial run before applying any new CLAs.  So if you run `matterport-dl.py --help` it will show `--no-tilde` as the option.  If you run `matterport-dl.py ASi1239a --help` and you already ran `ASi1239a` as a download with `--no-tilde` then `--help` will show `--tilde` as that is the negative.