Make sure to run matterport-dl.py with --debug any time you are trying to look into an issue.  It puts a bit more output to the console but doesn't hurt anything and can generate some helpful files.

Not sure we actually need cffi however as performance is better than the native requests lib we use it

previously we used a older style multi-thread concurrency setup.  This has been migrated to async functions but it means any blocking IO we missed can result in large slow downs on the critical functions

If we modify a file we should save the modified version as orig_name.modified.js as long as it ends in .html or .js we will automatically use .modified versions over original.  We want to preserve the original so we can re-run any post processing without redoing the entire download.

Originally a decent amount of work was for externally hosted support, this is somewhat de-prioritized now to making sure the internally served version works

Recently we added a new javascript proxy class [JSNetProxy.js] it allows us to avoid most manual modifications of scripts instead modifying requests at runtime to redirect to our local server.  It is a bit more foolproof to ensuring requests are only go to us.  It also is likely the best way to restore independent hosting outside of the internal engine as it can do things like modify POST requests to get requests.


Some failures are to be expected but a normal run looks something like:
Done, Total fetches: 33770 Skipped: 39 (0%) actual Request: 33731 (100%) Success: 33717 (100%) Failed403: 5 (0%) Failed404: 3 (0%) FailedUnknown: 0 (0%)

To ensure the proxy script is catching everything (and something isn't just using the hosted url) you can use socat to have a second part direct to the local server:
socat TCP4-LISTEN:9000,fork,reuseaddr TCP4:127.0.0.1:8080

then modify the matterport-dl.py to give the wrong port to JSNetProxy for the redirect

While we can likely enable plugins not originally enabled certain things are not possible if there is not the data.  For example floorplan sq/ft etc only exist if the original model collected the data it requires to compute that.

The CLI arg handling is a bit odd, as everything can have negative forms but sometimes the negative is the default the usage it shows is based on the opposite of the current value.   IE as we default to doing advanced download now there it shows the CLA as `--no-advanced-download` rather than `--advanced-download` and then somehow indicating it is on by default. This becomes a bit confusing if running an existing model.  If a model is passed and it has been run before we try to first load the CLAs that were loaded on the initial run before applying any new CLAs.  So if you run `matterport-dl.py --help` it will show `--no-tilde` as the option.  If you run `matterport-dl.py ASi1239a --help` and you already ran `ASi1239a` as a download with `--no-tilde` then `--help` will show `--tilde` as that is the negative.

Keys
Matterport uses access keys many places (t=*) args in the url.  With the wrong access key will get 403 even if the resource doesn't exist.  In addition they specify different access keys for the same resource many places (most don't work), some access keys may be short lived as well. Multiple access keys can work for one resource.  We currently replicate what the official client does in terms of which keys are used when, which should result in the least breakage.

To assist with keys we dump a file into debug/keys.txt that contains all the unique keys we extracted and which files they were found in (most may be not valid for anything).  The unix timestamp component of the key does not specify its expiry date and the expiry date can vary per key.  If you have a resource you want to access but can't you can use make a CLI call like: `matterport-dl.py EGxFGTFyC9N --debug --find-url-key "https://cdn-2.matterport.com/models/49b3e3ce762e4407b5bf1ea31b8e0a30/assets/5446c14bbc9946c0b6d548e36b0dcc51.dam?t=2-49fbb3bfa28f94f83d0ec381e3364030c1101d6a-1735633013-1"` and it will brute force every key it knows about to see if any will access that file successfully.

Nuclear Proxy Option
I sometimes use an internal proxy app with a real browser to test hybrid setups to determine why they are not working.  It can seamlessly save any resources the client requests to the normal matterport-dl.py path and just forwards all headers/requests to the normal target just like a normal http proxy.  I did debate moving to this as a step in duplicating a model. This has the benefit that it requires almost no knowledge of how matterport works to perfectly duplicate the resources needed.  You only need to do it once during capture, for it to get the key resources.  Beyond just letting the browser load the model you would need to change to dollhouse/floorplan views to make sure unique resources there would get loaded but would take less than a minute of time.  You would still want to have something that downloaded the full set of tiles/3d models/etc so you don't have to look at every single aspect of the model in the browser but this would be much less complex as the access keys could be taken from the similar requests the actual browser made for that item type.  So far changes have not warranted getting such a proxy into the code base but if complexity in adapting to changes is too much it may be an easy way to go.