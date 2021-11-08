#!/usr/bin/env python3

'''
Downloads virtual tours from matterport.
Usage is either running this program with the URL/pageid as an argument or calling the initiateDownload(URL/pageid) method.
'''

import requests
import json
import threading
import concurrent.futures
import urllib.request
from urllib.parse import urlparse
import pathlib
import re
import os
import shutil
import sys
import time
import logging
from tqdm import tqdm
from http.server import HTTPServer, SimpleHTTPRequestHandler
import decimal



# Weird hack
accessurls = []

def makeDirs(dirname):
    pathlib.Path(dirname).mkdir(parents=True, exist_ok=True)

def getVariants():
    variants = []
    depths = ["512", "1k", "2k", "4k"]
    for depth in range(4):
        z = depths[depth]
        for x in range(2**depth):
            for y in range(2**depth):
                for face in range(6):
                    variants.append(f"{z}_face{face}_{x}_{y}.jpg")
    return variants

def downloadUUID(accessurl, uuid):
    downloadFile(accessurl.format(filename=f'{uuid}_50k.dam'), f'{uuid}_50k.dam')
    shutil.copy(f'{uuid}_50k.dam', f'..{os.path.sep}{uuid}_50k.dam')
    cur_file=""
    try:
        for i in range(1000):
            cur_file=accessurl.format(filename=f'{uuid}_50k_texture_jpg_high/{uuid}_50k_{i:03d}.jpg')
            downloadFile(cur_file, f'{uuid}_50k_texture_jpg_high/{uuid}_50k_{i:03d}.jpg')
            cur_file=accessurl.format(filename=f'{uuid}_50k_texture_jpg_low/{uuid}_50k_{i:03d}.jpg')
            downloadFile(cur_file, f'{uuid}_50k_texture_jpg_low/{uuid}_50k_{i:03d}.jpg')
    except Exception as ex:
        logging.warning(f'Exception downloading file: {cur_file} of: {str(ex)}')
        pass #very lazy and bad way to only download required files

def downloadSweeps(accessurl, sweeps):
    with tqdm(total=(len(sweeps)*len(getVariants()))) as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
            for sweep in sweeps:
                for variant in getVariants():
                    pbar.update(1)
                    executor.submit(downloadFile, accessurl.format(filename=f'tiles/{sweep}/{variant}') + "&imageopt=1", f'tiles/{sweep}/{variant}')
                    while executor._work_queue.qsize() > 64:
                        time.sleep(0.01)

def downloadFileWithJSONPost(url, file, post_json_str, descriptor):
    global PROXY
    if "/" in file:
        makeDirs(os.path.dirname(file))
    if os.path.exists(file): #skip already downloaded files except idnex.html which is really json possibly wit hnewer access keys?
        logging.debug(f'Skipping json post to url: {url} ({descriptor}) as already downloaded')

    opener = getUrlOpener(PROXY)
    opener.addheaders.append(('Content-Type','application/json'))

    req = urllib.request.Request(url)

    for header in opener.addheaders: #not sure why we can't use the opener itself but it doesn't override it properly
        req.add_header(header[0],header[1])

    body_bytes = bytes(post_json_str, "utf-8")
    req.add_header('Content-Length', len(body_bytes))
    resp = urllib.request.urlopen(req, body_bytes)
    with open(file, 'w', encoding="UTF-8") as the_file:
        the_file.write(resp.read().decode("UTF-8"))
    logging.debug(f'Successfully downloaded w/ JSON post to: {url} ({descriptor}) to: {file}')


def downloadFile(url, file, post_data=None):
    global accessurls
    url = GetOrReplaceKey(url,False)

    if "/" in file:
        makeDirs(os.path.dirname(file))
    if "?" in file:
        file = file.split('?')[0]

    if os.path.exists(file): #skip already downloaded files except idnex.html which is really json possibly wit hnewer access keys?
        logging.debug(f'Skipping url: {url} as already downloaded')
        return;
    try:
        _filename,headers = urllib.request.urlretrieve(url, file,None,post_data)
        logging.debug(f'Successfully downloaded: {url} to: {file}')
        return
    except urllib.error.HTTPError as err:
        logging.warning(f'URL error dling {url} of will try alt: {str(err)}')

        # Try again but with different accessurls (very hacky!)
        if "?t=" in url:
            for accessurl in accessurls:
                url2=""
                try:
                    url2=f"{url.split('?')[0]}?{accessurl}"
                    urllib.request.urlretrieve(url2, file)
                    logging.debug(f'Successfully downloaded through alt: {url2} to: {file}')
                    return
                except urllib.error.HTTPError as err:
                    logging.warning(f'URL error alt method tried url {url2} dling of: {str(err)}')
                    pass
        logging.error(f'Failed to succeed for url {url}')
        raise Exception
    logging.error(f'Failed2 to succeed for url {url}')#hopefully not getting here?

def downloadGraphModels(pageid):
    global GRAPH_DATA_REQ
    makeDirs("api/mp/models")

    for key in GRAPH_DATA_REQ:
        file_path = f"api/mp/models/graph_{key}.json"
        downloadFileWithJSONPost("https://my.matterport.com/api/mp/models/graph",file_path, GRAPH_DATA_REQ[key], key)


def downloadAssets(base):
    js_files = ["showcase","browser-check","79","134","136","164","250","321","356","423","464","524","539","614","764","828","833","947"]
    language_codes = ["af", "sq", "ar-SA", "ar-IQ", "ar-EG", "ar-LY", "ar-DZ", "ar-MA", "ar-TN", "ar-OM",
     "ar-YE", "ar-SY", "ar-JO", "ar-LB", "ar-KW", "ar-AE", "ar-BH", "ar-QA", "eu", "bg",
     "be", "ca", "zh-TW", "zh-CN", "zh-HK", "zh-SG", "hr", "cs", "da", "nl", "nl-BE", "en",
     "en-US", "en-EG", "en-AU", "en-GB", "en-CA", "en-NZ", "en-IE", "en-ZA", "en-JM",
     "en-BZ", "en-TT", "et", "fo", "fa", "fi", "fr", "fr-BE", "fr-CA", "fr-CH", "fr-LU",
     "gd", "gd-IE", "de", "de-CH", "de-AT", "de-LU", "de-LI", "el", "he", "hi", "hu",
     "is", "id", "it", "it-CH", "ja", "ko", "lv", "lt", "mk", "mt", "no", "pl",
     "pt-BR", "pt", "rm", "ro", "ro-MO", "ru", "ru-MI", "sz", "sr", "sk", "sl", "sb",
     "es", "es-AR", "es-GT", "es-CR", "es-PA", "es-DO", "es-MX", "es-VE", "es-CO",
     "es-PE", "es-EC", "es-CL", "es-UY", "es-PY", "es-BO", "es-SV", "es-HN", "es-NI",
     "es-PR", "sx", "sv", "sv-FI", "th", "ts", "tn", "tr", "uk", "ur", "ve", "vi", "xh",
     "ji", "zu"];
    font_files = ["ibm-plex-sans-100", "ibm-plex-sans-100italic", "ibm-plex-sans-200", "ibm-plex-sans-200italic", "ibm-plex-sans-300",
    "ibm-plex-sans-300italic", "ibm-plex-sans-500", "ibm-plex-sans-500italic", "ibm-plex-sans-600", "ibm-plex-sans-600italic",
    "ibm-plex-sans-700", "ibm-plex-sans-700italic", "ibm-plex-sans-italic", "ibm-plex-sans-regular", "mp-font", "roboto-100", "roboto-100italic",
    "roboto-300", "roboto-300italic", "roboto-500", "roboto-500italic", "roboto-700", "roboto-700italic", "roboto-900", "roboto-900italic",
    "roboto-italic", "roboto-regular"]

    #extension assumed to be .png unless it is .svg or .jpg, for anything else place it in assets
    image_files = ["360_placement_pin_maskH", "chrome", "Desktop-help-play-button.svg", "Desktop-help-spacebar", "edge", "escape", "exterior",
    "exterior_hover", "firefox", "headset-cardboard", "headset-quest", "interior", "interior_hover", "matterport-logo-light.svg",
    "mattertag-disc-128-free.v1", "mobile-help-play-button.svg", "nav_help_360", "nav_help_click_inside", "nav_help_gesture_drag",
    "nav_help_gesture_drag_two_finger", "nav_help_gesture_pinch", "nav_help_gesture_position", "nav_help_gesture_position_two_finger",
    "nav_help_gesture_tap", "nav_help_inside_key", "nav_help_keyboard_all", "nav_help_keyboard_left_right", "nav_help_keyboard_up_down",
    "nav_help_mouse_click", "nav_help_mouse_drag_left", "nav_help_mouse_drag_right", "nav_help_mouse_position_left",
    "nav_help_mouse_position_right", "nav_help_mouse_zoom", "nav_help_tap_inside", "nav_help_zoom_keys", "NoteColor", "NoteIcon", "pinAnchor",
    "puck_256_red", "roboto-700-42_0", "safari", "scope.svg", "showcase-password-background.jpg", "surface_grid_planar_256", "tagbg", "tagmask",
    "vert_arrows"]

    assets = ["css/showcase.css", "css/unsupported_browser.css", "cursors/grab.png", "cursors/grabbing.png", "cursors/zoom-in.png",
    "cursors/zoom-out.png", "locale/strings.json",]

    for image in image_files:
        if not image.endswith(".jpg") and not image.endswith(".svg"):
            image = image + ".png"
        assets.append("images/" + image)
    for js in js_files:
        assets.append("js/" + js + ".js")
    for f in font_files:
        assets.extend(["fonts/" + f + ".woff", "fonts/" + f + ".woff2"])
    for lc in language_codes:
        assets.append("locale/messages/strings_" + lc + ".json")
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        for asset in assets:
            local_file = asset
            if local_file.endswith('/'):
                local_file = local_file    + "index.html"
            executor.submit(downloadFile, f"{base}{asset}", local_file)

def setAccessURLs(pageid):
    global accessurls
    with open(f"api/player/models/{pageid}/files_type2", "r", encoding="UTF-8") as f:
        filejson = json.load(f)
        accessurls.append(filejson["base.url"].split("?")[-1])
    with open(f"api/player/models/{pageid}/files_type3", "r", encoding="UTF-8") as f:
        filejson = json.load(f)
        accessurls.append(filejson["templates"][0].split("?")[-1])

def downloadInfo(pageid):
    assets = [f"api/v1/jsonstore/model/highlights/{pageid}", f"api/v1/jsonstore/model/Labels/{pageid}", f"api/v1/jsonstore/model/mattertags/{pageid}", f"api/v1/jsonstore/model/measurements/{pageid}", f"api/v1/player/models/{pageid}/thumb?width=1707&dpr=1.5&disable=upscale", f"api/v1/player/models/{pageid}/", f"api/v2/models/{pageid}/sweeps", "api/v2/users/current", f"api/player/models/{pageid}/files"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        for asset in assets:
            local_file = asset
            if local_file.endswith('/'):
                local_file = local_file    + "index.html"
            executor.submit(downloadFile, f"https://my.matterport.com/{asset}", local_file    )
    makeDirs("api/mp/models")
    with open(f"api/mp/models/graph", "w", encoding="UTF-8") as f:
        f.write('{"data": "empty"}')
    for i in range(1,4):
        downloadFile(f"https://my.matterport.com/api/player/models/{pageid}/files?type={i}", f"api/player/models/{pageid}/files_type{i}")
    setAccessURLs(pageid)

def downloadPics(pageid):
    with open(f"api/v1/player/models/{pageid}/index.html", "r", encoding="UTF-8") as f:
        modeldata = json.load(f)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        for image in modeldata["images"]:
            executor.submit(downloadFile, image["src"], urlparse(image["src"]).path[1:])

def downloadModel(pageid,accessurl):
    global ADVANCED_DOWNLOAD_ALL
    with open(f"api/v1/player/models/{pageid}/index.html", "r", encoding="UTF-8") as f:
        modeldata = json.load(f)
    accessid = re.search(r'models/([a-z0-9-_./~]*)/\{filename\}', accessurl).group(1)
    makeDirs(f"models/{accessid}")
    os.chdir(f"models/{accessid}")
    downloadUUID(accessurl,modeldata["job"]["uuid"])
    downloadSweeps(accessurl, modeldata["sweeps"])


# Patch showcase.js to fix expiration issue
def patchShowcase():
    with open("js/showcase.js","r",encoding="UTF-8") as f:
        j = f.read()
    j = re.sub(r"\&\&\(!e.expires\|\|.{1,10}\*e.expires>Date.now\(\)\)","",j)
    j = j.replace(f'"/api/mp/','`${window.location.pathname}`+"api/mp/')
    j = j.replace("${this.baseUrl}", "${window.location.origin}${window.location.pathname}")
    j = j.replace('e.get("https://static.matterport.com/geoip/",{responseType:"json",priority:n.RequestPriority.LOW})', '{"country_code":"US","country_name":"united states","region":"CA","city":"los angeles"}')
    with open("js/showcase.js","w",encoding="UTF-8") as f:
        f.write(j)

def drange(x, y, jump):
  while x < y:
    yield float(x)
    x += decimal.Decimal(jump)

KNOWN_ACCESS_KEY=None
def GetOrReplaceKey(url, is_read_key):
    global KNOWN_ACCESS_KEY
    key_regex = r'(t=2\-.+?\-0)'
    match = re.search(key_regex,url)
    if match is None:
        return url
    url_key = match.group(1)
    if KNOWN_ACCESS_KEY is None and is_read_key:
        KNOWN_ACCESS_KEY = url_key
    elif not is_read_key and KNOWN_ACCESS_KEY:
        url = url.replace(url_key, KNOWN_ACCESS_KEY)
    return url


def downloadPage(pageid):
    global ADVANCED_DOWNLOAD_ALL
    makeDirs(pageid)
    os.chdir(pageid)

    ADV_CROP_FETCH = [
            {
                "start":"width=512&crop=1024,1024,",
                "increment":'0.5'
            },
            {
                "start":"crop=512,512,",
               "increment":'0.25'
            }
        ]


    logging.basicConfig(filename='run_report.log', encoding='utf-8', level=logging.DEBUG,  format='%(asctime)s %(levelname)-8s %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
    logging.debug(f'Started up a download run')
    page_root_dir = os.path.abspath('.')
    print("Downloading base page...")
    r = requests.get(f"https://my.matterport.com/show/?m={pageid}")
    r.encoding = "utf-8"
    staticbase = re.search(r'<base href="(https://static.matterport.com/.*?)">', r.text).group(1)
    match = re.search(r'"(https://cdn-\d*\.matterport\.com/models/[a-z0-9\-_/.]*/)([{}0-9a-z_/<>.]+)(\?t=.*?)"', r.text)
    if match:
        accessurl = f'{match.group(1)}~/{{filename}}{match.group(3)}'
        print(accessurl)
    else:
        raise Exception("Can't find urls")


    file_type_content = requests.get(f"https://my.matterport.com/api/player/models/{pageid}/files?type=3") #get a valid access key, there are a few but this is a common client used one, this also makes sure it is fresh
    GetOrReplaceKey(file_type_content.text,True)
    if ADVANCED_DOWNLOAD_ALL:
        print("Doing advanced download of dollhouse/floorplan data...")
        ## Started to parse the modeldata further.  As it is error prone tried to try catch silently for failures. There is more data here we could use for example:
        ## queries.GetModelPrefetch.data.model.locations[X].pano.skyboxes[Y].tileUrlTemplate
        ## queries.GetModelPrefetch.data.model.locations[X].pano.skyboxes[Y].urlTemplate
        ## queries.GetModelPrefetch.data.model.locations[X].pano.resolutions[Y] <--- has the resolutions they offer for this one
        ## goal here is to move away from some of the access url hacks, but if we are successful on try one won't matter:)


        try:
            match = re.search(r'window.MP_PREFETCHED_MODELDATA = (\{.+?\}\}\});', r.text)
            if match:
                preload_json = json.loads(match.group(1))
                #download dam files
                base_node = preload_json["queries"]["GetModelPrefetch"]["data"]["model"]["assets"]
                for mesh in base_node["meshes"]:
                    try:
                        downloadFile(mesh["url"], urlparse(mesh["url"]).path[1:])#not expecting the non 50k one to work but mgiht as well try
                    except:
                        pass
                for texture in base_node["textures"]:
                    try: #on first exception assume we have all the ones needed
                        for i in range(1000):
                            full_text_url = texture["urlTemplate"].replace("<texture>",f'{i:03d}')
                            crop_to_do = []
                            if texture["quality"] == "high":
                                crop_to_do = ADV_CROP_FETCH
                            for crop in crop_to_do:
                                for x in list(drange(0, 1, decimal.Decimal(crop["increment"]))):
                                    for y in list(drange(0, 1, decimal.Decimal(crop["increment"]))):
                                        xs = f'{x}'
                                        ys = f'{y}'
                                        if xs.endswith('.0'):
                                            xs = xs[:-2]
                                        if ys.endswith('.0'):
                                            ys = ys[:-2]
                                        complete_add=f'{crop["start"]}x{xs},y{ys}'
                                        complete_add_file = complete_add.replace("&","_")
                                        try:
                                            downloadFile(full_text_url + "&" + complete_add, urlparse(full_text_url).path[1:] + complete_add_file + ".jpg")
                                        except:
                                            pass

                            downloadFile(full_text_url, urlparse(full_text_url).path[1:])
                    except:
                        pass
        except:
            pass
    # Automatic redirect if GET param isn't correct
    injectedjs = 'if (window.location.search != "?m=' + pageid + '") { document.location.search = "?m=' + pageid + '"; }'
    content = r.text.replace(staticbase,".").replace('"https://cdn-1.matterport.com/','`${window.location.origin}${window.location.pathname}` + "').replace('"https://mp-app-prod.global.ssl.fastly.net/','`${window.location.origin}${window.location.pathname}` + "').replace("window.MP_PREFETCHED_MODELDATA",f"{injectedjs};window.MP_PREFETCHED_MODELDATA").replace('"https://events.matterport.com/', '`${window.location.origin}${window.location.pathname}` + "')
    content = re.sub(r"validUntil\":\s*\"20[\d]{2}-[\d]{2}-[\d]{2}T","validUntil\":\"2099-01-01T",content)
    with open("index.html", "w", encoding="UTF-8") as f:
        f.write(content )

    print("Downloading static assets...")
    downloadAssets(staticbase)
    # Patch showcase.js to fix expiration issue
    patchShowcase()
    print("Downloading model info...")
    downloadInfo(pageid)
    print("Downloading images...")
    downloadPics(pageid)
    print("Downloading graph model data...")
    downloadGraphModels(pageid)
    print(f"Downloading model... access url: {accessurl}")
    downloadModel(pageid,accessurl)
    os.chdir(page_root_dir)
    open("api/v1/event", 'a').close()
    print("Done!")

def initiateDownload(url):
    downloadPage(getPageId(url))
def getPageId(url):
    return url.split("m=")[-1].split("&")[0]

class OurSimpleHTTPRequestHandler(SimpleHTTPRequestHandler):
    def send_error(self, code, message=None):
        if code == 404:
            logging.warning(f'404 error: {self.path} may not be downloading everything right')
        SimpleHTTPRequestHandler.send_error(self, code, message)

    def do_GET(self):
        redirect_msg=None
        orig_request = self.path
        if self.path.startswith("/locale/messages/strings_") and not os.path.exists(f".{self.path}"):
            redirect_msg = "original request was for a locale we do not have downloaded"
            self.path = "/locale/strings.json"
        raw_path, _, query = self.path.partition('?')
        if "crop=" in query and raw_path.endswith(".jpg"):
            query_args = urllib.parse.parse_qs(query)
            crop_addition = query_args.get("crop", None)
            if crop_addition is not None:
                crop_addition = f'crop={crop_addition[0]}'
            else:
                crop_addition = ''

            width_addition = query_args.get("width", None)
            if width_addition is not None:
                width_addition = f'width={width_addition[0]}_'
            else:
                width_addition = ''
            test_path = raw_path + width_addition + crop_addition + ".jpg"
            if os.path.exists(f".{test_path}"):
                self.path = test_path
                redirect_msg = "dollhouse/floorplan texture request that we have downloaded, better than generic texture file"
        if redirect_msg is not None or orig_request != self.path:
            logging.info(f'Redirecting {orig_request} => {self.path} as {redirect_msg}')



        SimpleHTTPRequestHandler.do_GET(self)
        return;
    def do_POST(self):
        post_msg=None
        try:
            if self.path == "/api/mp/models/graph":
                self.send_response(200)
                self.end_headers()
                content_len = int(self.headers.get('content-length'))
                post_body = self.rfile.read(content_len).decode('utf-8')
                json_body = json.loads(post_body)
                option_name = json_body["operationName"]
                if option_name in GRAPH_DATA_REQ:
                    file_path = f"api/mp/models/graph_{option_name}.json"
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="UTF-8") as f:
                            self.wfile.write(f.read().encode('utf-8'))
                            post_msg=f"graph of operationName: {option_name} we are handling internally"
                            return;
                    else:
                        post_msg=f"graph for operationName: {option_name} we don't know how to handle, but likely could add support, returning empty instead"

                self.wfile.write(bytes('{"data": "empty"}', "utf-8"))
                return
        except Exception as error:
            post_msg = f"Error trying to handle a post request of: {str(error)} this should not happen"
            pass
        finally:
            if post_msg is not None:
                logging.info(f'Handling a post request on {self.path}: {post_msg}')

        self.do_GET() #just treat the POST as a get otherwise:)

    def guess_type(self, path):
        res = SimpleHTTPRequestHandler.guess_type(self, path)
        if res == "text/html":
            return "text/html; charset=UTF-8"
        return res

PROXY=False
ADVANCED_DOWNLOAD_ALL=False

GRAPH_DATA_REQ = {}

def openDirReadGraphReqs(path,pageId):
    for root, dirs, filenames in os.walk(path):
        for file in filenames:
            with open(os.path.join(root, file), "r", encoding="UTF-8") as f:
                GRAPH_DATA_REQ[file.replace(".json","")] = f.read().replace("[MATTERPORT_MODEL_ID]",pageId)

def getUrlOpener(use_proxy):
    if (use_proxy):
        proxy = urllib.request.ProxyHandler({'http': use_proxy,'https': use_proxy})
        opener = urllib.request.build_opener(proxy)
    else:
        opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent','Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),('x-matterport-application-name','showcase')]
    return opener

def getCommandLineArg(name, has_value):
    for i in range(1,len(sys.argv)):
        if sys.argv[i] == name:
            sys.argv.pop(i)
            if has_value:
                return sys.argv.pop(i)
            else:
                return True
    return False

if __name__ == "__main__":
    ADVANCED_DOWNLOAD_ALL = getCommandLineArg("--advanced-download", False)
    PROXY = getCommandLineArg("--proxy", True)
    OUR_OPENER = getUrlOpener(PROXY)
    urllib.request.install_opener(OUR_OPENER)
    pageId = ""
    if len(sys.argv) > 1:
        pageId = getPageId(sys.argv[1])
    openDirReadGraphReqs("graph_posts",pageId)
    if len(sys.argv) == 2:
        initiateDownload(pageId)
    elif len(sys.argv) == 4:
        os.chdir(getPageId(pageId))
        logging.basicConfig(filename='server.log', encoding='utf-8', level=logging.DEBUG,  format='%(asctime)s %(levelname)-8s %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
        logging.info("Server started up")
        print ("View in browser: http://" + sys.argv[2] + ":" + sys.argv[3])
        httpd = HTTPServer((sys.argv[2], int(sys.argv[3])), OurSimpleHTTPRequestHandler)
        httpd.serve_forever()
    else:
        print (f"Usage:\n\tFirst Download: matterport-dl.py [url_or_page_id]\n\tThen launch the server 'matterport-dl.py [url_or_page_id] 127.0.0.1 8080' and open http://127.0.0.1:8080 in a browser\n\t--proxy 127.0.0.1:1234 -- to have it use this web proxy\n\t--advanced-download -- Use this option to try and download the cropped files for dollhouse/floorplan support")