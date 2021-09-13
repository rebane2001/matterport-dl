#!/usr/bin/env python3

'''
Downloads virtual tours from matterport.
Usage is either running this program with the URL/pageid as an argument or calling the initiateDownload(URL/pageid) method.
Output is a folder that can be hosted statically (eg python3 -m http.server) and visited in the browser without an internet connection.
Dollhouse view is a bit broken but everything else should work okayish.
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
from tqdm import tqdm

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
    try:
        for i in range(1000):
            downloadFile(accessurl.format(filename=f'{uuid}_50k_texture_jpg_high/{uuid}_50k_00{i}.jpg'), f'{uuid}_50k_texture_jpg_high/{uuid}_50k_00{i}.jpg')
            downloadFile(accessurl.format(filename=f'{uuid}_50k_texture_jpg_low/{uuid}_50k_00{i}.jpg'), f'{uuid}_50k_texture_jpg_low/{uuid}_50k_00{i}.jpg')
    except:
        pass #very lazy and bad way to only download required files

def downloadSweeps(accessurl, sweeps):
    with tqdm(total=(len(sweeps)*len(getVariants()))) as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
            for sweep in sweeps:
                for variant in getVariants():
                    pbar.update(1)
                    executor.submit(downloadFile, accessurl.format(filename=f'tiles/{sweep}/{variant}'), f'tiles/{sweep}/{variant}')
                    while executor._work_queue.qsize() > 64:
                        time.sleep(0.01)

def downloadFile(url, file):
    global accessurls
    if "/" in file:
        makeDirs(os.path.dirname(file))
    try:
        urllib.request.urlretrieve(url, file)
    except urllib.error.HTTPError:
        # Try again but with different accessurls (very hacky!)
        if "?t=" in url:
            for accessurl in accessurls:
                try:
                    urllib.request.urlretrieve(f"{url.split('?')[0]}?{accessurl}", file)
                    return
                except urllib.error.HTTPError:
                    pass
        raise Exception

def downloadAssets(base):
    assets = ["css/showcase.css", "css/unsupported_browser.css", "js/browser-check.js", "js/showcase.js", "js/134.js", "js/164.js", "js/833.js", "fonts/ibm-plex-sans-100.woff2", "fonts/ibm-plex-sans-100.woff", "fonts/ibm-plex-sans-100italic.woff2", "fonts/ibm-plex-sans-100italic.woff", "fonts/ibm-plex-sans-200.woff2", "fonts/ibm-plex-sans-200.woff", "fonts/ibm-plex-sans-200italic.woff2", "fonts/ibm-plex-sans-200italic.woff", "fonts/ibm-plex-sans-300.woff2", "fonts/ibm-plex-sans-300.woff", "fonts/ibm-plex-sans-300italic.woff2", "fonts/ibm-plex-sans-300italic.woff", "fonts/ibm-plex-sans-regular.woff2", "fonts/ibm-plex-sans-regular.woff", "fonts/ibm-plex-sans-italic.woff2", "fonts/ibm-plex-sans-italic.woff", "fonts/ibm-plex-sans-500.woff2", "fonts/ibm-plex-sans-500.woff", "fonts/ibm-plex-sans-500italic.woff2", "fonts/ibm-plex-sans-500italic.woff", "fonts/ibm-plex-sans-600italic.woff2", "fonts/ibm-plex-sans-600italic.woff", "fonts/ibm-plex-sans-600.woff2", "fonts/ibm-plex-sans-600.woff", "fonts/ibm-plex-sans-700.woff2", "fonts/ibm-plex-sans-700.woff", "fonts/ibm-plex-sans-700italic.woff2", "fonts/ibm-plex-sans-700italic.woff", "fonts/roboto-100.woff2", "fonts/roboto-100.woff", "fonts/roboto-100italic.woff2", "fonts/roboto-100italic.woff", "fonts/roboto-300.woff2", "fonts/roboto-300.woff", "fonts/roboto-300italic.woff2", "fonts/roboto-300italic.woff", "fonts/roboto-regular.woff2", "fonts/roboto-regular.woff", "fonts/roboto-italic.woff2", "fonts/roboto-italic.woff", "fonts/roboto-500.woff2", "fonts/roboto-500.woff", "fonts/roboto-500italic.woff2", "fonts/roboto-500italic.woff", "fonts/roboto-700.woff2", "fonts/roboto-700.woff", "fonts/roboto-700italic.woff2", "fonts/roboto-700italic.woff", "fonts/roboto-900.woff2", "fonts/roboto-900.woff", "fonts/roboto-900italic.woff2", "fonts/roboto-900italic.woff", "fonts/mp-font.woff2", "fonts/mp-font.woff", "fonts/mp-font.svg", "cursors/zoom-in.png", "cursors/zoom-out.png", "cursors/grab.png", "cursors/grabbing.png", "images/chrome.png", "images/edge.png", "images/firefox.png", "images/safari.png", "images/showcase-password-background.jpg", "images/matterport-logo-light.svg", "images/puck_256_red.png", "images/escape.png", "images/headset-cardboard.png", "images/headset-quest.png", "images/Desktop-help-play-button.svg", "images/Desktop-help-spacebar.png", "images/mattertag-disc-128-free.v1.png", "images/mobile-help-play-button.svg", "images/nav_help_360.png", "images/nav_help_click_inside.png", "images/nav_help_gesture_drag.png", "images/nav_help_gesture_drag_two_finger.png", "images/nav_help_gesture_pinch.png", "images/nav_help_gesture_position.png", "images/nav_help_gesture_position_two_finger.png", "images/nav_help_gesture_tap.png", "images/nav_help_inside_key.png", "images/nav_help_keyboard_all.png", "images/nav_help_keyboard_left_right.png", "images/nav_help_keyboard_up_down.png", "images/nav_help_mouse_click.png", "images/nav_help_mouse_drag_left.png", "images/nav_help_mouse_drag_right.png", "images/nav_help_mouse_position_left.png", "images/nav_help_mouse_position_right.png", "images/nav_help_mouse_zoom.png", "images/nav_help_tap_inside.png", "images/nav_help_zoom_keys.png", "images/tagbg.png", "images/tagmask.png", "images/NoteColor.png", "images/NoteIcon.png", "images/pinAnchor.png", "images/360_placement_pin_mask.png", "images/exterior.png", "images/exterior_hover.png", "images/interior.png", "images/interior_hover.png", "images/tagbg.png", "images/tagmask.png", "images/roboto-700-42_0.png",  "images/scope.svg",  "images/vert_arrows.png", "images/surface_grid_planar_256.png", "locale/strings-en-US.json"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        for asset in assets:
            executor.submit(downloadFile, f"{base}{asset}", asset)

def setAccessURLs(pageid):
    global accessurls
    with open(f"api/player/models/{pageid}/files_type2", "r", encoding="UTF-8") as f:
        filejson = json.load(f)
        accessurls.append(filejson["base.url"].split("?")[-1])
    with open(f"api/player/models/{pageid}/files_type3", "r", encoding="UTF-8") as f:
        filejson = json.load(f)
        accessurls.append(filejson["templates"][0].split("?")[-1])

def downloadInfo(pageid):
    assets = [f"api/v1/jsonstore/model/highlights/{pageid}", f"api/v1/jsonstore/model/Labels/{pageid}", f"api/v1/jsonstore/model/mattertags/{pageid}", f"api/v1/jsonstore/model/measurements/{pageid}", f"api/v1/player/models/{pageid}", f"api/v2/models/{pageid}/sweeps", "api/v2/users/current", f"api/player/models/{pageid}/files"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        for asset in assets:
            executor.submit(downloadFile, f"https://my.matterport.com/{asset}", asset)
    makeDirs("api/mp/models")
    with open(f"api/mp/models/graph", "w", encoding="UTF-8") as f:
        f.write('{"data": "empty"}')
    for i in range(1,4):
        downloadFile(f"https://my.matterport.com/api/player/models/{pageid}/files?type={i}", f"api/player/models/{pageid}/files_type{i}")
    setAccessURLs(pageid)

def downloadPics(pageid):
    with open(f"api/v1/player/models/{pageid}", "r", encoding="UTF-8") as f:
        modeldata = json.load(f)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        for image in modeldata["images"]:
            executor.submit(downloadFile, image["src"], urlparse(image["src"]).path[1:])

def downloadModel(pageid,accessurl):
    with open(f"api/v1/player/models/{pageid}", "r", encoding="UTF-8") as f:
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


def downloadPage(pageid):
    makeDirs(pageid)
    os.chdir(pageid)
    print("Downloading base page...")
    r = requests.get(f"https://my.matterport.com/show/?m={pageid}")
    staticbase = re.search(r'<base href="(https://static.matterport.com/.*?)">', r.text).group(1)
    match = re.search(r'"(https://cdn-\d*\.matterport\.com/models/[a-z0-9\-_/.]*/)([{}0-9a-z_/<>.]+)(\?t=.*?)"', r.text)
    if match:
        accessurl = f'{match.group(1)}~/{{filename}}{match.group(3)}'
        print(accessurl)
    else:
        raise Exception("Can't find urls")
    # Automatic redirect if GET param isn't correct
    injectedjs = 'if (window.location.search != "?m=' + pageid + '") { document.location.search = "?m=' + pageid + '"; }'
    content = r.text.replace(staticbase,".").replace('"https://cdn-1.matterport.com/','`${window.location.origin}${window.location.pathname}` + "').replace('"https://mp-app-prod.global.ssl.fastly.net/','`${window.location.origin}${window.location.pathname}` + "').replace("window.MP_PREFETCHED_MODELDATA",f"{injectedjs};window.MP_PREFETCHED_MODELDATA").replace('"https://events.matterport.com/', '`${window.location.origin}${window.location.pathname}` + "')
    with open("index.html", "w", encoding="UTF-8") as f:
        f.write(content)
    print("Downloading static assets...")
    downloadAssets(staticbase)
    # Patch showcase.js to fix expiration issue
    patchShowcase()
    print("Downloading model info...")
    downloadInfo(pageid)
    print("Downloading images...")
    downloadPics(pageid)
    print("Downloading model...")
    downloadModel(pageid,accessurl)
    print("Done!")

def initiateDownload(url):
    downloadPage(url.split("m=")[-1].split("&")[0])

if __name__ == "__main__":
    if len(sys.argv) == 2:
        initiateDownload(sys.argv[1])
