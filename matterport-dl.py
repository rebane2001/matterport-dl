#!/usr/bin/env python3
# ruff: noqa: E722

"""
Downloads virtual tours from matterport.
Usage is either running this program with the URL/pageid as an argument or calling the initiateDownload(URL/pageid) method.
"""

from __future__ import annotations
import urllib.parse
from curl_cffi import requests
from enum import Enum
import asyncio
import aiofiles
import json
import threading
import urllib.request
from urllib.parse import urlparse
import pathlib
import re
import os
import platform

import shutil
import sys
from typing import Any, Self, TypeVar, ClassVar, cast
from dataclasses import dataclass

import logging
from tqdm import tqdm
from http.server import HTTPServer, SimpleHTTPRequestHandler
import decimal

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


BASE_MATTERPORTDL_DIR = pathlib.Path(__file__).resolve().parent
MAX_CONCURRENT_REQUESTS = 20  # cffi will make sure no more than this many curl workers are used at once
MAX_CONCURRENT_TASKS = 64  # while we could theoretically leave this unbound just relying on MAX_CONCURRENT_REQESTS there is little reason to spawn a million tasks at once

BASE_MATTERPORT_DOMAIN = "matterport.com"
CHINA_MATTERPORT_DOMAIN = "matterportvr.cn"

# Matterport uses various access keys for a page, when the primary key doesnt work we try some other ones,  note a single model can have 1400+ unique access keys not sure which matter vs not
accesskeys = []


dirsMadeCache: dict[str, bool] = {}
THIS_MODEL_ROOT_DIR : str

# modified from https://gist.github.com/pkienzle/5e13ec07077d32985fa48ebe43486832
def git_rev():
    """
    Get the git revision for the repo in the path *repo*.
    Returns the commit id of the current head.
    Note: this function parses the files in the git repository directory
    without using the git application.  It may break if the structure of
    the git repository changes.  It only reads files, so it should not do
    any damage to the repository in the process.
    """
    # Based on stackoverflow am9417
    # https://stackoverflow.com/questions/14989858/get-the-current-git-hash-in-a-python-script/59950703#59950703
    git_root = BASE_MATTERPORTDL_DIR / ".git"
    git_head = git_root / "HEAD"
    if not git_head.exists():
        return None

    # Read .git/HEAD file
    with git_head.open("r") as fd:
        head_ref = fd.read()

    # Find head file .git/HEAD (e.g. ref: ref/heads/master => .git/ref/heads/master)
    if not head_ref.startswith("ref: "):
        return head_ref
    head_ref = head_ref[5:].strip()

    # Read commit id from head file
    head_path = git_root.joinpath(*head_ref.split("/"))
    if not head_path.exists():
        return None

    with head_path.open("r") as fd:
        commit = fd.read().strip()

    return f"{head_ref} ({commit})"

def sys_info():
    str = "Running python "
    try:
        str += platform.python_version()
        str += " on " + sys.platform
        str += " with matterport-dl version: " + git_rev()
    except Exception:
        pass
    return str
    


def makeDirs(dirname):
    global dirsMadeCache
    if dirname in dirsMadeCache:
        return
    pathlib.Path(dirname).mkdir(parents=True, exist_ok=True)
    dirsMadeCache[dirname] = True


def consoleDebugLog(msg: str, loglevel=logging.INFO, forceDebugOn=False):
    logging.log(loglevel,msg)
    if not CLA.getCommandLineArg(CommandLineArg.CONSOLE_LOG) and (forceDebugOn or CLA.getCommandLineArg(CommandLineArg.DEBUG) ):
        print(msg)

def consoleLog(msg: str, loglevel=logging.INFO):
    consoleDebugLog(msg,loglevel,True)


def getModifiedName(filename: str):
    filename, _, query = filename.partition("?")
    basename = filename
    ext = ""
    pos = filename.rfind(".")
    if pos != -1:
        ext = basename[pos + 1 :]
        basename = basename[0:pos]
    if query:
        ext += "?" + query
    return f"{basename}.modified.{ext}"


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


async def downloadUUID(accessurl, uuid):
    await downloadFile("UUID_DAM50K", True, accessurl.format(filename=f"{uuid}_50k.dam"), f"{uuid}_50k.dam")
    shutil.copy(f"{uuid}_50k.dam", f"..{os.path.sep}{uuid}_50k.dam")
    cur_file = ""
    try:
        for i in range(1000):  # basically download until on first failure and assume that is all of them, maybe we should be going to on first 404 or osmething:)
            cur_file = accessurl.format(filename=f"{uuid}_50k_texture_jpg_high/{uuid}_50k_{i:03d}.jpg")
            await downloadFile("UUID_TEXTURE_HIGH", True, cur_file, f"{uuid}_50k_texture_jpg_high/{uuid}_50k_{i:03d}.jpg")
            cur_file = accessurl.format(filename=f"{uuid}_50k_texture_jpg_low/{uuid}_50k_{i:03d}.jpg")
            await downloadFile("UUID_TEXTURE_LOW", True, cur_file, f"{uuid}_50k_texture_jpg_low/{uuid}_50k_{i:03d}.jpg")
    except Exception as ex:
        logging.warning(f"Exception downloading file: {cur_file} of: {str(ex)}")
        pass  # very lazy and bad way to only download required files


async def downloadSweeps(accessurl, sweeps):
    toDownload: list[AsyncDownloadItem] = []
    for sweep in sweeps:
        sweep = sweep.replace("-", "")
        for variant in getVariants():
            toDownload.append(AsyncDownloadItem("MODEL_SWEEPS", True, accessurl.format(filename=f"tiles/{sweep}/{variant}") + "&imageopt=1", f"tiles/{sweep}/{variant}"))
    await AsyncArrayDownload(toDownload)


async def downloadFileWithJSONPostAndGetText(type, shouldExist, url, file, post_json_str, descriptor, always_download=False):
    if not CLA.getCommandLineArg(CommandLineArg.TILDE):
        file = file.replace("~", "_")

    await downloadFileWithJSONPost(type, shouldExist, url, file, post_json_str, descriptor, always_download)
    if not os.path.exists(file):
        return ""
    else:
        async with aiofiles.open(file, "r", encoding="UTF-8") as f:
            return await f.read()


async def downloadFileWithJSONPost(type, shouldExist, url, file, post_json_str, descriptor, always_download=False):
    global OUR_SESSION
    if not CLA.getCommandLineArg(CommandLineArg.TILDE):
        file = file.replace("~", "_")
    if "/" in file:
        makeDirs(os.path.dirname(file))

    if not CLA.getCommandLineArg(CommandLineArg.DOWNLOAD) or (os.path.exists(file) and not always_download):  # skip already downloaded files except index.html which is really json possibly wit hnewer access keys?
        logUrlDownloadSkipped(type, file, url, descriptor)
        return

    reqId = logUrlDownloadStart(type, file, url, descriptor, shouldExist)
    try:
        resp: requests.Response = await OUR_SESSION.request(url=url, method="POST", headers={"Content-Type": "application/json"}, data=bytes(post_json_str, "utf-8"))
        resp.raise_for_status()
        # req.add_header('Content-Length', len(body_bytes))
        async with aiofiles.open(file, "wb") as the_file:
            await the_file.write(resp.content)
        logUrlDownloadFinish(type, file, url, descriptor, shouldExist, reqId)
    except Exception as ex:
        logUrlDownloadFinish(type, file, url, descriptor, shouldExist, reqId, ex)
        raise Exception(f"Request error for url: {url} ({type}) that would output to: {file}") from ex


async def GetTextOnlyRequest(type, shouldExist, url, post_data=None) -> str:
    global PROGRESS
    useTmpFileName = ""
    async with aiofiles.tempfile.NamedTemporaryFile(delete_on_close=False) as tmpFile:  # type: ignore
        useTmpFileName = cast(str, tmpFile.name)

    result = await downloadFileAndGetText(type, shouldExist, url, useTmpFileName, post_data)
    PROGRESS.Increment(ProgressType.Request, -1)
    PROGRESS.Increment(ProgressType.Success, -1)
    try:
        os.remove(useTmpFileName)
    except:
        pass
    return result


async def downloadFileAndGetText(type, shouldExist, url, file, post_data=None, isBinary=False, always_download=False):
    if not CLA.getCommandLineArg(CommandLineArg.TILDE):
        file = file.replace("~", "_")

    await downloadFile(type, shouldExist, url, file, post_data, always_download)
    if not os.path.exists(file):
        return ""
    else:
        readMode = "r"
        encoding = "UTF-8"
        if isBinary:
            readMode = "rb"
            encoding = None
        async with aiofiles.open(file, readMode, encoding=encoding) as f:  # type: ignore - r and rb are handled but by diff overload groups
            return await f.read()


# Add type parameter, shortResourcePath, shouldExist
async def downloadFile(type, shouldExist, url, file, post_data=None, always_download=False):
    global accesskeys, MAX_TASKS_SEMAPHORE, OUR_SESSION
    async with MAX_TASKS_SEMAPHORE:
        url = GetOrReplaceKey(url, False)

        if not CLA.getCommandLineArg(CommandLineArg.TILDE):
            file = file.replace("~", "_")

        if "/" in file:
            makeDirs(os.path.dirname(file))
        if "?" in file:
            file = file.split("?")[0]

        if not CLA.getCommandLineArg(CommandLineArg.DOWNLOAD) or (os.path.exists(file) and not always_download):  # skip already downloaded files except idnex.html which is really json possibly wit hnewer access keys?
            logUrlDownloadSkipped(type, file, url, "")
            return
        reqId = logUrlDownloadStart(type, file, url, "", shouldExist)
        try:
            response = await OUR_SESSION.get(url)
            response.raise_for_status()  # Raise an exception if the response has an error status code
            async with aiofiles.open(file, "wb") as f:
                await f.write(response.content)
            logUrlDownloadFinish(type, file, url, "", shouldExist, reqId)
            return
        except Exception as err:
            # Try again but with different accesskeys
            if "?t=" in url:
                for accessurl in accesskeys:
                    url2 = ""
                    try:
                        url2 = f"{url.split('?')[0]}?{accessurl}"
                        response = await OUR_SESSION.get(url2)
                        response.raise_for_status()  # Raise an exception if the response has an error status code

                        async with aiofiles.open(file, "wb") as f:
                            await f.write(response.content)
                        logUrlDownloadFinish(type, file, url2, "", shouldExist, reqId)
                        return
                    except Exception as err2:
                        logUrlDownloadFinish(type, file, url2, "", shouldExist, reqId, err2, True)
                        pass
            logUrlDownloadFinish(type, file, url, "", shouldExist, reqId, err)
            raise Exception(f"Request error for url: {url} ({type}) that would output to: {file}") from err


def validUntilFix(text):
    return re.sub(r"validUntil\"\s*:\s*\"20[\d]{2}-[\d]{2}-[\d]{2}T", 'validUntil":"2099-01-01T', text)

async def downloadGraphModels(pageid):
    global GRAPH_DATA_REQ, BASE_MATTERPORT_DOMAIN
    makeDirs("api/mp/models")

    for key in GRAPH_DATA_REQ:
        file_path_base = f"api/mp/models/graph_{key}"
        file_path = f"{file_path_base}.json"
        text = await downloadFileWithJSONPostAndGetText("GRAPH_MODEL", True, f"https://my.{BASE_MATTERPORT_DOMAIN}/api/mp/models/graph", file_path, GRAPH_DATA_REQ[key], key, CLA.getCommandLineArg(CommandLineArg.ALWAYS_DOWNLOAD_GRAPH_REQS))

        # Patch (graph_GetModelDetails.json & graph_GetSnapshots.json and such) URLs to Get files form local server instead of https://cdn-2.matterport.com/
        if CLA.getCommandLineArg(CommandLineArg.MANUAL_HOST_REPLACEMENT):
            text = text.replace(f"https://cdn-2.{BASE_MATTERPORT_DOMAIN}", "http://127.0.0.1:8080")  # without the localhost it seems like it may try to do diff
            text = text.replace(f"https://cdn-1.{BASE_MATTERPORT_DOMAIN}", "http://127.0.0.1:8080")  # without the localhost it seems like it may try to do diff
        text = validUntilFix(text)

        async with aiofiles.open(getModifiedName(file_path), "w", encoding="UTF-8") as f:
            await f.write(text)


ProgressType = Enum("ProgressType", ["Request", "Success", "Skipped", "Failed404", "Failed403", "FailedUnknown"])


class ProgressStats:
    def __str__(self):
        relInfo = ""
        if self.relativeTo is not None:
            relInfo = "Relative "
        return f"{relInfo}Total fetches: {self.TotalPosRequests()} {self.ValStr(ProgressType.Skipped)} actual {self.ValStr(ProgressType.Request)} {self.ValStr(ProgressType.Success)} {self.ValStr(ProgressType.Failed403)} {self.ValStr(ProgressType.Failed404)} {self.ValStr(ProgressType.FailedUnknown)}"

    def RelativeMark(self):
        self.relativeTo = dict(self.stats)
    def ClearRelative(self):
        self.relativeTo = None

    relativeTo: dict[ProgressType, int] | None
    def __init__(self):
        self.stats: dict[ProgressType, int] = dict()
        # self.locks : dict[ProgressType,asyncio.Semaphore] = dict()
        self.locks: dict[ProgressType, threading.Lock] = dict()
        for typ in ProgressType:
            self.stats[typ] = 0
            self.locks[typ] = threading.Lock()

    def Val(self, typ: ProgressType):
        val = self.stats[typ]
        if self.relativeTo is not None:
            val -= self.relativeTo[typ]
        return val

    def TotalPosRequests(self):
        return self.Val(ProgressType.Request) + self.Val(ProgressType.Skipped)

    def ValStr(self, typ: ProgressType):
        val = self.Val(typ)
        perc = f" ({val/self.TotalPosRequests():.0%})"
        return f"{typ.name}: {self.Val(typ)}{perc}"

    def Increment(self, typ: ProgressType, amt: int = 1):
        with self.locks[typ]:
            self.stats[typ] += 1
            return self.stats[typ]


PROGRESS = ProgressStats()


def logUrlDownloadFinish(type, localTarget, url, additionalParams, shouldExist, requestID, error=None, altUrlExists=False):
    global PROGRESS
    logLevel = logging.INFO
    prefix = "Finished"
    if error:
        if altUrlExists:
            logLevel = logging.WARNING
            error = f"PartErr of: {error}"
            prefix = "aTryFail"
        else:
            logLevel = logging.ERROR
            error = f"Error of: {error}"
            prefix = "aFailure"
            PROGRESS.Increment(ProgressType.Failed403 if "403" in error else ProgressType.Failed404 if "404" in error else ProgressType.FailedUnknown)
    else:
        PROGRESS.Increment(ProgressType.Success)
        error = ""
    _logUrlDownload(logLevel, prefix, type, localTarget, url, additionalParams, shouldExist, requestID, error)  # not sure if should lower log elve for shouldExist  false


def logUrlDownloadSkipped(type, localTarget, url, additionalParams):
    global PROGRESS
    PROGRESS.Increment(ProgressType.Skipped)
    _logUrlDownload(logging.DEBUG, "Skipped already downloaded", type, localTarget, url, additionalParams, False, "")


def logUrlDownloadStart(type, localTarget, url, additionalParams, shouldExist):
    global PROGRESS
    ourReqId = PROGRESS.Increment(ProgressType.Request)
    _logUrlDownload(logging.DEBUG, "Starting", type, localTarget, url, additionalParams, shouldExist, ourReqId)
    return ourReqId


def _logUrlDownload(logLevel, logPrefix, type, localTarget, url, additionalParams, shouldExist, requestID, optionalResult=None):
    global CLA
    if not CLA.getCommandLineArg(CommandLineArg.DOWNLOAD):
        return
    if optionalResult:
        optionalResult = f"Result: {optionalResult}"
    else:
        optionalResult = ""

    logging.log(logLevel, f"{logPrefix} REQ for {type} {requestID}: should exist: {shouldExist} {optionalResult} File: {localTarget} at url: {url} {additionalParams}")


async def downloadAssets(base):
    global PROGRESS, BASE_MATTERPORT_DOMAIN

    # not really used any more unless we run into bad results
    numeric_js_files = [30, 39, 46, 47, 58, 62, 66, 76, 79, 134, 136, 143, 164, 207, 250, 251, 260, 300, 309, 316, 321, 330, 356, 371, 376, 383, 385, 386, 393, 399, 422, 423, 438, 464, 519, 521, 524, 525, 539, 564, 580, 584, 606, 614, 633, 666, 670, 674, 718, 721, 726, 755, 764, 769, 794, 828, 833, 838, 856, 926, 932, 933, 934, 947, 976, 995]

    language_codes = ["af", "sq", "ar-SA", "ar-IQ", "ar-EG", "ar-LY", "ar-DZ", "ar-MA", "ar-TN", "ar-OM", "ar-YE", "ar-SY", "ar-JO", "ar-LB", "ar-KW", "ar-AE", "ar-BH", "ar-QA", "eu", "bg", "be", "ca", "zh-TW", "zh-CN", "zh-HK", "zh-SG", "hr", "cs", "da", "nl", "nl-BE", "en", "en-US", "en-EG", "en-AU", "en-GB", "en-CA", "en-NZ", "en-IE", "en-ZA", "en-JM", "en-BZ", "en-TT", "et", "fo", "fa", "fi", "fr", "fr-BE", "fr-CA", "fr-CH", "fr-LU", "gd", "gd-IE", "de", "de-CH", "de-AT", "de-LU", "de-LI", "el", "he", "hi", "hu", "is", "id", "it", "it-CH", "ja", "ko", "lv", "lt", "mk", "mt", "no", "pl", "pt-BR", "pt", "rm", "ro", "ro-MO", "ru", "ru-MI", "sz", "sr", "sk", "sl", "sb", "es", "es-AR", "es-GT", "es-CR", "es-PA", "es-DO", "es-MX", "es-VE", "es-CO", "es-PE", "es-EC", "es-CL", "es-UY", "es-PY", "es-BO", "es-SV", "es-HN", "es-NI", "es-PR", "sx", "sv", "sv-FI", "th", "ts", "tn", "tr", "uk", "ur", "ve", "vi", "xh", "ji", "zu"]
    font_files = ["ibm-plex-sans-100", "ibm-plex-sans-100italic", "ibm-plex-sans-200", "ibm-plex-sans-200italic", "ibm-plex-sans-300", "ibm-plex-sans-300italic", "ibm-plex-sans-500", "ibm-plex-sans-500italic", "ibm-plex-sans-600", "ibm-plex-sans-600italic", "ibm-plex-sans-700", "ibm-plex-sans-700italic", "ibm-plex-sans-italic", "ibm-plex-sans-regular", "mp-font", "roboto-100", "roboto-100italic", "roboto-300", "roboto-300italic", "roboto-500", "roboto-500italic", "roboto-700", "roboto-700italic", "roboto-900", "roboto-900italic", "roboto-italic", "roboto-regular"]

    # extension assumed to be .png unless it is .svg or .jpg, for anything else place it in assets
    image_files = ["360_placement_pin_mask", "chrome", "Desktop-help-play-button.svg", "Desktop-help-spacebar", "edge", "escape", "exterior", "exterior_hover", "firefox", "headset-cardboard", "headset-quest", "interior", "interior_hover", "matterport-logo-light.svg", "matterport-logo.svg", "mattertag-disc-128-free.v1", "mobile-help-play-button.svg", "nav_help_360", "nav_help_click_inside", "nav_help_gesture_drag", "nav_help_gesture_drag_two_finger", "nav_help_gesture_pinch", "nav_help_gesture_position", "nav_help_gesture_position_two_finger", "nav_help_gesture_tap", "nav_help_inside_key", "nav_help_keyboard_all", "nav_help_keyboard_left_right", "nav_help_keyboard_up_down", "nav_help_mouse_click", "nav_help_mouse_ctrl_click", "nav_help_mouse_drag_left", "nav_help_mouse_drag_right", "nav_help_mouse_position_left", "nav_help_mouse_position_right", "nav_help_mouse_zoom", "nav_help_tap_inside", "nav_help_zoom_keys", "NoteColor", "NoteIcon", "pinAnchor", "puck_256_red", "roboto-700-42_0", "safari", "scope.svg", "showcase-password-background.jpg", "surface_grid_planar_256", "tagbg", "tagmask", "vert_arrows", "headset-quest-2", "pinIconDefault", "tagColor", "matterport-app-icon.svg"]

    assets = ["js/browser-check.js", "css/showcase.css", "css/scene.css", "css/unsupported_browser.css", "cursors/grab.png", "cursors/grabbing.png", "cursors/zoom-in.png", "cursors/zoom-out.png", "locale/strings.json", "css/ws-blur.css", "css/core.css", "css/split.css", "css/late.css", "matterport-logo.svg"]

    # downloadFile("my.matterport.com/favicon.ico", "favicon.ico")
    file = "js/showcase.js"
    typeDict = {file: "STATIC_JS"}
    await downloadFile("STATIC_ASSET", True, f"https://matterport.com/nextjs-assets/images/favicon.ico", "favicon.ico")  # mainly to avoid the 404, always matterport.com
    showcase_cont = await downloadFileAndGetText(typeDict[file], True, base + file, file, always_download=True)

    # lets try to extract the js files it might be loading and make sure we know them
    js_extracted = re.findall(r"\.e\(([0-9]{2,3})\)", showcase_cont)
    js_extracted.sort()
    for asset in assets:
        typeDict[asset] = "STATIC_ASSET"

    for js in numeric_js_files:
        file = f"js/{js}.js"
        typeDict[file] = "STATIC_JS"
        assets.append(file)

    for js in js_extracted:
        file = f"js/{js}.js"
        if file not in assets:
            typeDict[file] = "DISCOVERED_JS"
            assets.append(file)

    for image in image_files:
        if not image.endswith(".jpg") and not image.endswith(".svg"):
            image = image + ".png"
        file = "images/" + image
        typeDict[file] = "STATIC_IMAGE"
        assets.append(file)

    for f in font_files:
        for file in ["fonts/" + f + ".woff", "fonts/" + f + ".woff2"]:
            typeDict[file] = "STATIC_FONT"
            assets.append(file)
    for lc in language_codes:
        file = "locale/messages/strings_" + lc + ".json"
        typeDict[file] = "STATIC_LOCAL_STRINGS"
        assets.append(file)

    toDownload: list[AsyncDownloadItem] = []
    for asset in assets:
        local_file = asset
        type = typeDict[asset]
        if local_file.endswith("/"):
            local_file = local_file + "index.html"
        shouldExist = True
        # if type.startswith("BRUTE"):
        #     shouldExist = False
        toDownload.append(AsyncDownloadItem(type, shouldExist, f"{base}{asset}", local_file))
    await AsyncArrayDownload(toDownload)

    toDownload.clear()
    if CLA.getCommandLineArg(CommandLineArg.BRUTE_JS):
        for x in range(1, 1000):
            file = f"js/{x}.js"
            if file not in assets:
                toDownload.append(AsyncDownloadItem("BRUTE_JS", False, f"{base}{file}", file))
                assets.append(file)
        before = PROGRESS.Val(ProgressType.Success)
        consoleLog("Brute force additional JS files...")
        await AsyncArrayDownload(toDownload)


async def downloadWebglVendors(urls):
    for url in urls:
        await downloadFile("WEBGL_FILE", False, url, urlparse(url).path[1:])


def setAccessURLs(pageid):
    global accesskeys
    with open(f"api/player/models/{pageid}/files_type2", "r", encoding="UTF-8") as f:
        filejson = json.load(f)
        accesskeys.append(filejson["base.url"].split("?")[-1])
    with open(f"api/player/models/{pageid}/files_type3", "r", encoding="UTF-8") as f:
        filejson = json.load(f)
        accesskeys.append(filejson["templates"][0].split("?")[-1])


class AsyncDownloadItem:
    def __init__(self, type: str, shouldExist: bool, url: str, file: str):
        self.type = type
        self.shouldExist = shouldExist
        self.url = url
        self.file = file


class ExceptionWhatExceptionTaskGroup(asyncio.TaskGroup):
    def __init__(self):
        super().__init__()
        self._parent_cancel_requested = True  # hacky but required to prevent an aborted task from stopping us from being async

    def _abort(self):  # normally it goes through and cancels all the others now
        return None

    async def __aexit__(self, et, exc, tb):  # at end of block it would throw any exceptions
        try:
            await super().__aexit__(et, exc, tb)
        except:
            pass


async def AsyncArrayDownload(assets: list[AsyncDownloadItem]):
    # with tqdm(total=(len(assets))) as pbar:
    async with ExceptionWhatExceptionTaskGroup() as tg:
        PROGRESS.RelativeMark()
        
        for asset in tqdm(assets):
            # pbar.update(1)
            tg.create_task(downloadFile(asset.type, asset.shouldExist, asset.url, asset.file))
            await asyncio.sleep(0.001)  # we need some sleep or we will not yield
            while MAX_TASKS_SEMAPHORE.locked():
                await asyncio.sleep(0.01)
        logging.debug(f"{PROGRESS}")

async def downloadInfo(pageid):
    global BASE_MATTERPORT_DOMAIN
    assets = [f"api/v1/jsonstore/model/highlights/{pageid}", f"api/v1/jsonstore/model/Labels/{pageid}", f"api/v1/jsonstore/model/mattertags/{pageid}", f"api/v1/jsonstore/model/measurements/{pageid}", f"api/v1/player/models/{pageid}/thumb?width=1707&dpr=1.5&disable=upscale", f"api/v1/player/models/{pageid}/", f"api/v2/models/{pageid}/sweeps", "api/v2/users/current", f"api/player/models/{pageid}/files", f"api/v1/jsonstore/model/trims/{pageid}", "api/v1/plugins?manifest=true", f"api/v1/jsonstore/model/plugins/{pageid}"]
    toDownload: list[AsyncDownloadItem] = []
    for asset in assets:
        local_file = asset
        if local_file.endswith("/"):
            local_file = local_file + "index.html"
        toDownload.append(AsyncDownloadItem("MODEL_INFO", True, f"https://my.{BASE_MATTERPORT_DOMAIN}/{asset}", local_file))
    await AsyncArrayDownload(toDownload)

    makeDirs("api/mp/models")
    with open("api/mp/models/graph", "w", encoding="UTF-8") as f:
        f.write('{"data": "empty"}')
    for i in range(1, 4):  # file to url mapping
        await downloadFile("FILE_TO_URL_JSON", True, f"https://my.{BASE_MATTERPORT_DOMAIN}/api/player/models/{pageid}/files?type={i}", f"api/player/models/{pageid}/files_type{i}")
    setAccessURLs(pageid)


async def downloadPlugins(pageid):
    global BASE_MATTERPORT_DOMAIN
    pluginJson: Any
    with open("api/v1/plugins", "r", encoding="UTF-8") as f:
        pluginJson = json.loads(f.read())
    for plugin in pluginJson:
        plugPath = f"showcase-sdk/plugins/published/{plugin["name"]}/{plugin["currentVersion"]}/plugin.json"
        await downloadFile("PLUGIN", True, f"https://static.{BASE_MATTERPORT_DOMAIN}/{plugPath}", plugPath)


async def downloadPics(pageid):
    # All these should already be downloaded through AdvancedAssetDownload likely they wont work here without a different access key any more....
    with open(f"api/v1/player/models/{pageid}/index.html", "r", encoding="UTF-8") as f:
        modeldata = json.load(f)
    toDownload: list[AsyncDownloadItem] = []
    for image in modeldata["images"]:
        toDownload.append(AsyncDownloadItem("MODEL_IMAGES", True, image["src"], urlparse(image["src"]).path[1:]))  # want want to use signed_src or download_url?
    await AsyncArrayDownload(toDownload)


async def downloadMainAssets(pageid, accessurl):
    global THIS_MODEL_ROOT_DIR
    with open(f"api/v1/player/models/{pageid}/index.html", "r", encoding="UTF-8") as f:
        modeldata = json.load(f)
    match = re.search(r"models/([a-z0-9-_./~]*)/\{filename\}", accessurl)
    if match is None:
        raise Exception(f"Unable to extract access model id from url: {accessurl}")
    accessid = match.group(1)
    basePath = f"models/{accessid}"
    if not CLA.getCommandLineArg(CommandLineArg.TILDE):
        basePath = basePath.replace("~", "_")
    makeDirs(basePath)
    os.chdir(basePath)
    await downloadUUID(accessurl, modeldata["job"]["uuid"])
    await downloadSweeps(accessurl, modeldata["sweeps"]) #sweeps are generally the biggest thing minus a few modles that have massive 3d detail items
    os.chdir(THIS_MODEL_ROOT_DIR)

# Patch showcase.js to fix expiration issue
def patchShowcase():
    global BASE_MATTERPORT_DOMAIN
    showcaseJs = "js/showcase.js"
    with open(showcaseJs, "r", encoding="UTF-8") as f:
        j = f.read()
    j = re.sub(r"\&\&\(!e.expires\|\|.{1,10}\*e.expires>Date.now\(\)\)", "", j)  # old
    j = j.replace("this.urlContainer.expires", "Date.now()")  # newer
    j = j.replace("this.onStale", "this.onStal")  # even newer
    if CLA.getCommandLineArg(CommandLineArg.MANUAL_HOST_REPLACEMENT):
        j = j.replace('"/api/mp/', '`${window.location.pathname}`+"api/mp/')
        j = j.replace("${this.baseUrl}", "${window.location.origin}${window.location.pathname}")

    j = j.replace(f'e.get("https://static.{BASE_MATTERPORT_DOMAIN}/geoip/",{{responseType:"json",priority:n.ru.LOW}})', '{"country_code":"US","country_name":"united states","region":"CA","city":"los angeles"}')
    if CLA.getCommandLineArg(CommandLineArg.MANUAL_HOST_REPLACEMENT):
        j = j.replace(f"https://static.{BASE_MATTERPORT_DOMAIN}", "")
    with open(getModifiedName(showcaseJs), "w", encoding="UTF-8") as f:
        f.write(j)


#    j = j.replace('"POST"','"GET"') #no post requests for external hosted
#    with open("js/showcase.js","w",encoding="UTF-8") as f:
#        f.write(j)


def drange(x, y, jump):
    while x < y:
        yield float(x)
        x += decimal.Decimal(jump)


KNOWN_ACCESS_KEY = None
KEY_REPLACE_ACTIVE = True


def EnableDisableKeyReplacement(enabled):
    global KEY_REPLACE_ACTIVE
    KEY_REPLACE_ACTIVE = enabled


def GetOrReplaceKey(url, is_read_key):
    global KNOWN_ACCESS_KEY, KEY_REPLACE_ACTIVE
    if not KEY_REPLACE_ACTIVE:
        return url
    # key_regex = r'(t=2\-.+?\-[0-9])(&|$|")'
    key_regex = r"(t=(.+?)&k)"
    match = re.search(key_regex, url)
    if match is None:
        return url
    url_key = match.group(1)
    if KNOWN_ACCESS_KEY is None and is_read_key:
        KNOWN_ACCESS_KEY = url_key
    elif not is_read_key and KNOWN_ACCESS_KEY:
        url = url.replace(url_key, KNOWN_ACCESS_KEY)
    return url


def DebugSaveFile(fileName, fileContent):
    consoleLog(f"Saved debug file: {fileName}")
    with open(f"debug/{fileName}", "w") as the_file:
        the_file.write(fileContent)


def RemoteDomainsReplace(str: str):
    global BASE_MATTERPORT_DOMAIN
    domReplace = [f"static.{BASE_MATTERPORT_DOMAIN}", f"cdn-2.{BASE_MATTERPORT_DOMAIN}", f"cdn-1.{BASE_MATTERPORT_DOMAIN}", "mp-app-prod.global.ssl.fastly.net", f"events.{BASE_MATTERPORT_DOMAIN}"]

    # str = str.replace('"https://static.matterport.com','`${window.location.origin}${window.location.pathname}` + "').replace('"https://cdn-2.matterport.com','`${window.location.origin}${window.location.pathname}` + "').replace('"https://cdn-1.matterport.com','`${window.location.origin}${window.location.pathname}` + "').replace('"https://mp-app-prod.global.ssl.fastly.net/','`${window.location.origin}${window.location.pathname}` + "').replace('"https://events.matterport.com/', '`${window.location.origin}${window.location.pathname}` + "')
    if CLA.getCommandLineArg(CommandLineArg.MANUAL_HOST_REPLACEMENT):
        for dom in domReplace:
            str = str.replace(f"https://{dom}", "http://127.0.0.1:8080")

    return str


async def downloadCapture(pageid):
    global KNOWN_ACCESS_KEY, PROGRESS, RUN_ARGS_CONFIG_NAME, BASE_MATTERPORT_DOMAIN, CHINA_MATTERPORT_DOMAIN, THIS_MODEL_ROOT_DIR
    makeDirs(pageid)
    alias = CLA.getCommandLineArg(CommandLineArg.ALIAS)
    if alias and not os.path.exists(alias):
        os.symlink(pageid, alias)
    THIS_MODEL_ROOT_DIR = os.path.abspath(pageid)
    os.chdir(THIS_MODEL_ROOT_DIR)
    ROOT_FILE_COPY = ["JSNetProxy.js", "matterport-dl.py"]
    for fl in ROOT_FILE_COPY:
        if not os.path.exists(fl):
            shutil.copy2(os.path.join(BASE_MATTERPORTDL_DIR, fl), fl)

    CLA.SaveToFile(RUN_ARGS_CONFIG_NAME)

    logging.basicConfig(filename="run_report.log", level=logging.DEBUG, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S", encoding="utf-8")

    if CLA.getCommandLineArg(CommandLineArg.DEBUG):
        makeDirs("debug")
    if CLA.getCommandLineArg(CommandLineArg.CONSOLE_LOG):
        logging.getLogger().addHandler(logging.StreamHandler())
    consoleLog(f"Started up a download run {sys_info()}")
    
    url = f"https://my.{BASE_MATTERPORT_DOMAIN}/show/?m={pageid}"
    consoleLog(f"Downloading capture of {pageid} with base page... {url}")
    base_page_text = ""
    try:
        base_page_text : str = await downloadFileAndGetText("MAIN", True, url, "index.html", always_download=True)
        if f"{CHINA_MATTERPORT_DOMAIN}/showcase" in base_page_text:
            BASE_MATTERPORT_DOMAIN = CHINA_MATTERPORT_DOMAIN
            consoleLog("Chinese matterport url found in main page, will try China server, note if this does not work try a proxy outside china")
        if CLA.getCommandLineArg(CommandLineArg.DEBUG):
            DebugSaveFile("base_page.html", base_page_text)  # noqa: E701

    except Exception as error:
        if "certificate verify failed" in str(error) or "SSL certificate problem" in str(error):
            raise TypeError(f"Error: {str(error)}. Have you tried running the Install Certificates.command (or similar) file in the python folder to install the normal root certs?") from error
        else:
            raise TypeError("First request error") from error

    staticbase = re.search(rf'<base href="(https://static.{BASE_MATTERPORT_DOMAIN}/.*?)">', base_page_text).group(1)  # type: ignore - may be None

    threeMin = re.search(r"https://static.matterport.com/webgl-vendors/three/[a-z0-9\-_/.]*/three.min.js", base_page_text).group()  # type: ignore - may be None , this is always.com
    dracoWasmWrapper = threeMin.replace("three.min.js", "libs/draco/gltf/draco_wasm_wrapper.js")
    dracoDecoderWasm = threeMin.replace("three.min.js", "libs/draco/gltf/draco_decoder.wasm")
    basisTranscoderWasm = threeMin.replace("three.min.js", "libs/basis/basis_transcoder.wasm")
    basisTranscoderJs = threeMin.replace("three.min.js", "libs/basis/basis_transcoder.js")
    webglVendors = [threeMin, dracoWasmWrapper, dracoDecoderWasm, basisTranscoderWasm, basisTranscoderJs]
    match = re.search(r'"(https://cdn-\d*\.matterport(?:vr)?\.(?:com|cn)/models/[a-z0-9\-_/.]*/)([{}0-9a-z_/<>.]+)(\?t=.*?)"', base_page_text.encode("utf-8", errors="ignore").decode("unicode-escape"))  # some non-english matterport pages have unicode escapes for even the generic url chars
#matterportvr.cn
    if match:
        accessurl = f"{match.group(1)}~/{{filename}}{match.group(3)}"

    else:
        raise Exception(f"Can't find urls, try the main page: {url} in a browser to make sure it loads the model correctly")

    # get a valid access key, there are a few but this is a common client used one, this also makes sure it is fresh
    file_type_content = await GetTextOnlyRequest("MAIN", True, f"https://my.{BASE_MATTERPORT_DOMAIN}/api/player/models/{pageid}/files?type=3")  # get a valid access key, there are a few but this is a common client used one, this also makes sure it is fresh
    GetOrReplaceKey(file_type_content, True)

    consoleLog("Downloading graph model data...")  # need the details one for advanced download
    await downloadGraphModels(pageid)

    if CLA.getCommandLineArg(CommandLineArg.ADVANCED_DOWNLOAD):
        await AdvancedAssetDownload(base_page_text)

    # Automatic redirect if GET param isn't correct
    forcedProxyBase = "window.location.origin"
    # forcedProxyBase='"http://127.0.0.1:9000"'
    injectedjs = 'if (window.location.search != "?m=' + pageid + '") { document.location.search = "?m=' + pageid + '"; };window._NoTilde=' + ("false" if CLA.getCommandLineArg(CommandLineArg.TILDE) else "true") + ";window._ProxyBase=" + forcedProxyBase + ";"
    content = base_page_text.replace(staticbase, ".")
    proxyAdd = ""
    if CLA.getCommandLineArg(CommandLineArg.MANUAL_HOST_REPLACEMENT):
        content = RemoteDomainsReplace(content)
    else:
        content = re.sub(r"(?P<preDomain>src\s*=\s*['" '"])https?://[^/"' "']+/", r"\g<preDomain>", content, flags=re.IGNORECASE)
        proxyAdd = "<script blocking='render' src='JSNetProxy.js'></script>"

    content = validUntilFix(content)
    content = content.replace("<head>", f"<head><script>{injectedjs}</script>{proxyAdd}")
    with open(getModifiedName("index.html"), "w", encoding="UTF-8") as f:
        f.write(content)

    consoleLog("Downloading static files...")

    await downloadAssets(staticbase)
    await downloadWebglVendors(webglVendors)
    # Patch showcase.js to fix expiration issue and some other changes for local hosting
    patchShowcase()
    consoleLog("Downloading model info...")
    await downloadInfo(pageid)
    consoleLog("Downloading plugins...")
    await downloadPlugins(pageid)
    consoleLog("Downloading images...")
    await downloadPics(pageid)
    open("api/v1/event", "a").close()
    if CLA.getCommandLineArg(CommandLineArg.MAIN_ASSET_DOWNLOAD):
        consoleLog("Downloading primary model assets...")
        await downloadMainAssets(pageid, accessurl)
    os.chdir(THIS_MODEL_ROOT_DIR)
    PROGRESS.ClearRelative()
    consoleLog(f"Done, {PROGRESS}!")


async def AdvancedAssetDownload(base_page_text: str):
    ADV_CROP_FETCH = [{"start": "width=512&crop=1024,1024,", "increment": "0.5"}, {"start": "crop=512,512,", "increment": "0.25"}]
    consoleLog("Doing advanced download of dollhouse/floorplan data...")
    # Started to parse the modeldata further.  As it is error prone tried to try catch silently for failures. There is more data here we could use for example:
    # queries.GetModelPrefetch.data.model.locations[X].pano.skyboxes[Y].tileUrlTemplate
    # queries.GetModelPrefetch.data.model.locations[X].pano.skyboxes[Y].urlTemplate
    # queries.GetModelPrefetch.data.model.locations[X].pano.resolutions[Y] <--- has the resolutions they offer for this one
    # goal here is to move away from some of the access url hacks, but if we are successful on try one won't matter:)
    EnableDisableKeyReplacement(False)

    try:
        base_node: Any = None  # lets try to use this now first seems to be more accurate the precache key can be invalid in comparison
        base_cache_node: Any = None
        base_node_snapshots: Any = None
        try:
            with open("api/mp/models/graph_GetModelDetails.json", "r", encoding="UTF-8") as f:
                graphModelDetailsJson = json.loads(f.read())
                base_node = graphModelDetailsJson["data"]["model"]
        except Exception:
            logging.exception("Unable to open graph model details output json something probably wrong.....")

        try:
            with open("api/mp/models/graph_GetSnapshots.json", "r", encoding="UTF-8") as f:
                graphModelSnapshotsJson = json.loads(f.read())
                base_node_snapshots = graphModelSnapshotsJson["data"]["model"]
        except Exception:
            logging.exception("Unable to open graph model for snapshots output json something probably wrong.....")

        match = re.search(r"window.MP_PREFETCHED_MODELDATA = (\{.+?\}\}\});", base_page_text)
        preload_json_str = ""
        if not match:
            match = re.search(r"window.MP_PREFETCHED_MODELDATA = parseJSON\((\"\{.+?\}\}\}\")\);", base_page_text)  # this happens for extra unicode encoded pages
            preload_json_str = json.loads(match.group(1))
        else:
            preload_json_str = match.group(1)

        if match:
            preload_json = json.loads(preload_json_str)  # in theory this json should be similar to GetModelDetails, sometimes it is a bit different so we may want to switch
            base_cache_node = preload_json["queries"]["GetModelPrefetch"]["data"]["model"]

        if CLA.getCommandLineArg(CommandLineArg.DEBUG):
            DebugSaveFile("advanced_model_data_extracted.json", json.dumps(base_cache_node, indent="\t"))  # noqa: E701
            DebugSaveFile("advanced_model_data_from_GetModelDetails.json", json.dumps(base_node, indent="\t"))  # noqa: E701
            DebugSaveFile("advanced_model_data_from_GetSnapshots.json", json.dumps(base_node_snapshots, indent="\t"))  # noqa: E701

        if not base_cache_node:
            base_cache_node = base_node
        if not base_node:
            base_node = base_cache_node
        if "locations" not in base_node:  # the query doesnt get locations back but the cahce does have it
            base_node["locations"] = base_cache_node["locations"]

        toDownload: list[AsyncDownloadItem] = []
        consoleDebugLog(f"AdvancedDownload photos: {len(base_node_snapshots["assets"]["photos"])} meshes: {len(base_node["assets"]["meshes"])}, locations: {len(base_node["locations"])}, tileset indexes: {len(base_node["assets"]["tilesets"])}, textures: {len(base_node["assets"]["textures"])}, ")

        for mesh in base_node["assets"]["meshes"]:
            toDownload.append(AsyncDownloadItem("ADV_MODEL_MESH", "50k" not in mesh["url"], mesh["url"], urlparse(mesh["url"]).path[1:]))  # not expecting the non 50k one to work but mgiht as well try

        for photo in base_node_snapshots["assets"]["photos"]:
            toDownload.append(AsyncDownloadItem("ADV_MODEL_IMAGES", True, photo["presentationUrl"], urlparse(photo["presentationUrl"]).path[1:]))

        # Download GetModelPrefetch.data.model.locations[X].pano.skyboxes[Y].urlTemplate
        for location in base_node["locations"]:
            for skybox in location["pano"]["skyboxes"]:
                try:
                    for face in range(6):
                        skyboxUrlTemplate = skybox["urlTemplate"].replace("<face>", f"{face}")
                        toDownload.append(AsyncDownloadItem("ADV_SKYBOX", False, skyboxUrlTemplate, urlparse(skyboxUrlTemplate).path[1:]))
                except:
                    pass

        consoleLog("Going to download tileset 3d asset models")
        # Download Tilesets
        for tileset in base_node["assets"]["tilesets"]:  # normally just one tileset
            tilesetUrl = tileset["url"]
            tilesetUrlTemplate: str = tileset["urlTemplate"]
            if "<file>" not in tilesetUrlTemplate:  # the graph details does have it but the cached data does not
                tilesetUrlTemplate = tilesetUrlTemplate.replace("?", "<file>?")
            tilesetBaseFile = urlparse(tilesetUrl).path[1:]
            try:
                tileSetBytes = await downloadFileAndGetText("ADV_TILESET", False, tilesetUrl, tilesetBaseFile, isBinary=True)
                tileSetText = tileSetBytes.decode("utf-8", "ignore")
                # tileSetText = validUntilFix(tileSetText)
                # with open(getModifiedName(tilesetBaseFile), "w", encoding="UTF-8") as f:
                # f.write(tileSetText)

                uris = re.findall(r'"uri":"(.+?)"', tileSetText)  # a bit brutish to extract rather than just walking the json

                uris.sort()

                for uri in tqdm(uris):
                    url = tilesetUrlTemplate.replace("<file>", uri)
                    try:
                        chunkBytes = await downloadFileAndGetText("ADV_TILESET_GLB", False, url, urlparse(url).path[1:], isBinary=True)
                        chunkText = chunkBytes.decode("utf-8", "ignore")
                        chunks = re.findall(r"(lod[0-9]_[a-zA-Z0-9-_]+\.(jpg|ktx2))", chunkText)
                        # print("Found chunks: ",chunks)
                        chunks.sort()
                        for ktx2 in chunks:
                            chunkUri = f"{uri[:2]}{ktx2[0]}"
                            chunkUrl = tilesetUrlTemplate.replace("<file>", chunkUri)
                            toDownload.append(AsyncDownloadItem("ADV_TILESET_TEXTURE", False, chunkUrl, urlparse(chunkUrl).path[1:]))

                    except:
                        raise
            except:
                raise

            for file in range(6):
                try:
                    tileseUrlTemplate = tilesetUrlTemplate.replace("<file>", f"{file}.json")
                    getFileText = await downloadFileAndGetText("ADV_TILESET_JSON", False, tileseUrlTemplate, urlparse(tileseUrlTemplate).path[1:])
                    fileUris = re.findall(r'"uri":"(.*?)"', getFileText)
                    fileUris.sort()
                    for fileuri in fileUris:
                        fileUrl = tilesetUrlTemplate.replace("<file>", fileuri)
                        try:
                            toDownload.append(AsyncDownloadItem("ADV_TILESET_EXTRACT", False, fileUrl, urlparse(fileUrl).path[1:]))
                        except:
                            pass

                except:
                    pass

        for texture in base_node["assets"]["textures"]:
            try:  # on first exception assume we have all the ones needed so cant use array download as need to know which fails (other than for crops)
                for i in range(1000):
                    full_text_url = texture["urlTemplate"].replace("<texture>", f"{i:03d}")
                    crop_to_do = []
                    if texture["quality"] == "high":
                        crop_to_do = ADV_CROP_FETCH
                    for crop in crop_to_do:
                        for x in list(drange(0, 1, decimal.Decimal(crop["increment"]))):
                            for y in list(drange(0, 1, decimal.Decimal(crop["increment"]))):
                                xs = f"{x}"
                                ys = f"{y}"
                                if xs.endswith(".0"):
                                    xs = xs[:-2]
                                if ys.endswith(".0"):
                                    ys = ys[:-2]
                                complete_add = f'{crop["start"]}x{xs},y{ys}'
                                complete_add_file = complete_add.replace("&", "_")
                                toDownload.append(AsyncDownloadItem("ADV_TEXTURE_CROPPED", False, full_text_url + "&" + complete_add, urlparse(full_text_url).path[1:] + complete_add_file + ".jpg"))  # failures here ok we dont know all teh crops that exist, so we can still use the array downloader
                    try:
                        await downloadFile("ADV_TEXTURE_FULL", True, full_text_url, urlparse(full_text_url).path[1:])
                    except:
                        break
            except Exception:
                logging.exception("Adv download texture have exception")
        consoleLog("Downloading textures and previews for tileset 3d models")
        await AsyncArrayDownload(toDownload)
    except Exception:
        logging.exception("Adv download general had exception of")
        if CLA.getCommandLineArg(CommandLineArg.DEBUG):
            raise
        else:
            pass
    EnableDisableKeyReplacement(True)


async def initiateDownload(url):
    try:
        async with OUR_SESSION:
            await downloadCapture(getPageId(url))
    except Exception:
        logging.exception("Unhandled fatal exception")
        raise


def getPageId(url):
    id = url.split("m=")[-1].split("&")[0]
    if not id.isalnum() or len(id) < 5 or len(id) > 15:
        raise Exception(f"Likely invalid model id extracted: {id} from your input of: {url} you should pass the ID itself (ie EGxFGTFyC9N) or the url: form like: https://my.matterport.com/show/?m=EGxFGTFyC9N")
    return id



class OurSimpleHTTPRequestHandler(SimpleHTTPRequestHandler):
    def send_error(self, code, message=None, explain=None):
        if code == 404:
            consoleLog(f"###### 404 error: {self.path} may not be downloading everything right", logging.WARNING)
        SimpleHTTPRequestHandler.send_error(self, code, message, explain)

    def log_request(self, code='-', size='-'):
        if CLA.getCommandLineArg(CommandLineArg.QUIET) and code == 200:
            return
        SimpleHTTPRequestHandler.log_request(self,code,size)

    def end_headers(self):
        self.send_my_headers()
        SimpleHTTPRequestHandler.end_headers(self)

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_my_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        if self.isPotentialModifiedFile():
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")

    def getRawPath(self):
        raw_path, _, query = self.path.partition("?")
        return raw_path

    def getQuery(self):
        raw_path, _, query = self.path.partition("?")
        return query

    def do_GET(self):
        global BASE_MATTERPORTDL_DIR
        redirect_msg = None
        orig_request = self.path
        if not CLA.getCommandLineArg(CommandLineArg.TILDE):
            self.path = self.path.replace("~", "_")

        orig_raw_path = raw_path = self.getRawPath()
        query = self.getQuery()

        if raw_path.endswith("/"):
            raw_path += "index.html"

        if raw_path.startswith("/JSNetProxy.js"):
            logging.info("Using our javascript network proxier")
            self.send_response(200)
            self.end_headers()
            with open(os.path.join(BASE_MATTERPORTDL_DIR, "JSNetProxy.js"), "r", encoding="UTF-8") as f:
                self.wfile.write(f.read().encode("utf-8"))
                return

        if raw_path.startswith("/locale/messages/strings_") and not os.path.exists(f".{raw_path}"):
            redirect_msg = "original request was for a locale we do not have downloaded"
            raw_path = "/locale/strings.json"

        if "crop=" in query and raw_path.endswith(".jpg"):
            query_args = urllib.parse.parse_qs(query)
            crop_addition = query_args.get("crop", None)
            if crop_addition is not None:
                crop_addition = f"crop={crop_addition[0]}"
            else:
                crop_addition = ""

            width_addition = query_args.get("width", None)
            if width_addition is not None:
                width_addition = f"width={width_addition[0]}_"
            else:
                width_addition = ""
            test_path = raw_path + width_addition + crop_addition + ".jpg"
            if os.path.exists(f".{test_path}"):
                raw_path = test_path
                redirect_msg = "dollhouse/floorplan texture request that we have downloaded, better than generic texture file"

        if raw_path != orig_raw_path:
            self.path = raw_path
        if self.isPotentialModifiedFile():
            posFile = getModifiedName(self.path)
            if os.path.exists(posFile[1:]):
                self.path = posFile
                redirect_msg = "modified version exists"

        if redirect_msg is not None or orig_request != self.path:
            logging.info(f"Redirecting {orig_request} => {self.path} as {redirect_msg}")
        SimpleHTTPRequestHandler.do_GET(self)

    def isPotentialModifiedFile(self):
        posModifiedExt = ["js", "json", "html"]
        raw_path = self.getRawPath()
        for ext in posModifiedExt:
            if raw_path.endswith(f".{ext}"):
                return True
        return False

    def do_POST(self):
        post_msg = None
        logLevel = logging.INFO
        try:
            if urlparse(self.path).path == "/api/mp/models/graph":
                self.send_response(200)
                self.end_headers()
                content_len = int(self.headers.get("content-length") or "0")
                post_body = self.rfile.read(content_len).decode("utf-8")
                json_body = json.loads(post_body)
                option_name = json_body["operationName"]
                if option_name in GRAPH_DATA_REQ:
                    file_path = f"api/mp/models/graph_{option_name}.json"
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="UTF-8") as f:
                            self.wfile.write(f.read().encode("utf-8"))
                            post_msg = f"graph of operationName: {option_name} we are handling internally"
                            return
                    else:
                        logLevel = logging.WARNING
                        post_msg = f"graph for operationName: {option_name} we don't know how to handle, but likely could add support, returning empty instead. If you get an error this may be why (include this message in bug report)."

                self.wfile.write(bytes('{"data": "empty"}', "utf-8"))
                return
        except Exception as error:
            logLevel = logging.ERROR
            post_msg = f"Error trying to handle a post request of: {str(error)} this should not happen"
            pass
        finally:
            if post_msg is not None:
                logging.log(logLevel, f"Handling a post request on {self.path}: {post_msg}")

        self.do_GET()  # just treat the POST as a get otherwise:)

    def guess_type(self, path):
        res = SimpleHTTPRequestHandler.guess_type(self, path)
        if res == "text/html":
            return "text/html; charset=UTF-8"
        return res


GRAPH_DATA_REQ = {}
OUR_SESSION: requests.AsyncSession
MAX_TASKS_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
RUN_ARGS_CONFIG_NAME = "run_args.json"


def openDirReadGraphReqs(path, pageId):
    for root, dirs, filenames in os.walk(path):
        for file in filenames:
            lfile = file.lower()
            if not lfile.startswith("get") or not lfile.endswith(".json"): #fixes evil osx files
                continue
            with open(os.path.join(root, file), "r", encoding="UTF-8") as f:
                if "modified" in file:
                    continue
                GRAPH_DATA_REQ[file.replace(".json", "")] = f.read().replace("[MATTERPORT_MODEL_ID]", pageId)


def SetupSession(use_proxy):
    global OUR_SESSION, MAX_CONCURRENT_REQUESTS, BASE_MATTERPORT_DOMAIN
    OUR_SESSION = requests.AsyncSession(impersonate="chrome", max_clients=MAX_CONCURRENT_REQUESTS, verify=CLA.getCommandLineArg(CommandLineArg.VERIFY_SSL), proxies=({"http": use_proxy, "https": use_proxy} if use_proxy else None), headers={"Referer": f"https://my.{BASE_MATTERPORT_DOMAIN}/", "x-matterport-application-name": "showcase"})


def RegisterWindowsBrowsers():
    """Read the installed browsers from the Windows registry."""
    # https://github.com/python/cpython/issues/52479
    import winreg

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Clients\StartMenuInternet") as hkey:
        i = 0
        while True:
            try:
                subkey = winreg.EnumKey(hkey, i)
                i += 1
            except OSError as e:
                if e.winerror != 259:  # ERROR_NO_MORE_ITEMS
                    raise
                break
            try:
                name = winreg.QueryValue(hkey, subkey)
                if not name or not isinstance(name, str):
                    name = subkey
            except OSError:
                name = subkey
            try:
                cmd = winreg.QueryValue(hkey, rf"{subkey}\shell\open\command")
                cmd = cmd.strip('"')
                os.stat(cmd)
            except (OSError, AttributeError, TypeError, ValueError):
                cmd = ""
            name = name.replace("Google ", "").replace("Mozilla ", "").replace("Microsoft ", "")  # emulate stock names
            webbrowser.register(name, None, webbrowser.GenericBrowser(cmd))


CommandLineArg = Enum("CommandLineArg", ["ADVANCED_DOWNLOAD", "PROXY", "VERIFY_SSL", "DEBUG", "CONSOLE_LOG", "BRUTE_JS", "TILDE", "BASE_FOLDER", "ALIAS", "DOWNLOAD", "MAIN_ASSET_DOWNLOAD", "MANUAL_HOST_REPLACEMENT", "ALWAYS_DOWNLOAD_GRAPH_REQS","QUIET", "HELP", "ADV_HELP", "AUTO_SERVE"])
ArgAppliesTo = Enum("ArgAppliesTo", ["DOWNLOAD", "SERVING", "BOTH"])


@dataclass
class CLA:
    arg: CommandLineArg
    description: str
    hasValue: bool
    itemValueHelpDisplay: str
    defaultValue: Any
    currentValue: Any
    hidden: bool
    allow_saving: bool
    applies_to: ArgAppliesTo
    all_args: ClassVar[list[CLA]] = []
    orig_args: ClassVar[list[str]] = []  # we store them so we can reparse them after a config load
    value_cache: ClassVar[dict[CommandLineArg, Any]] = {}  # faster lookup

    @staticmethod
    def addCommandLineArg(arg: CommandLineArg, description: str, defaultValue: Any, itemValueHelpDisplay: str = "", hidden=False, allow_saved=True, applies_to=ArgAppliesTo.DOWNLOAD):
        """itemValueHelpDisplay is the name to show in help for after the --arg   ie for --proxy '127.0.0.1:8080'"""
        cla = CLA(arg=arg, currentValue=defaultValue, defaultValue=defaultValue, description=description, hasValue=itemValueHelpDisplay != "", itemValueHelpDisplay=itemValueHelpDisplay, hidden=hidden, allow_saving=allow_saved, applies_to=applies_to)
        if len(CLA.orig_args) == 0:
            CLA.orig_args = sys.argv.copy()
        for i in range(len(sys.argv) - 1, -1, -1):
            isNegativeName = sys.argv[i] == f"--no-{cla.argConsoleName()}"
            if sys.argv[i] == f"--{cla.argConsoleName()}" or isNegativeName:
                sys.argv.pop(i)
                if cla.hasValue and not isNegativeName:
                    sys.argv.pop(i)
        CLA.all_args.append(cla)

    @staticmethod
    def parseArgs():
        CLA.value_cache = {}
        for i in range(1, len(CLA.orig_args)):
            for cla in CLA.all_args:
                isNegativeName = CLA.orig_args[i] == f"--no-{cla.argConsoleName()}"
                if CLA.orig_args[i] == f"--{cla.argConsoleName()}" or isNegativeName:
                    if cla.hasValue:
                        cla.currentValue = CLA.orig_args[i + 1] if not isNegativeName else ""
                    else:
                        cla.currentValue = not isNegativeName

    def argConsoleName(self):
        return self.arg.name.replace("_", "-").lower()

    @staticmethod
    def LoadFromFile(file: str):
        with open(file, "r", encoding="UTF-8") as f:
            config = json.loads(f.read())
            for arg in CLA.all_args:
                if arg.arg.name in config:
                    arg.currentValue = config[arg.arg.name]

    @staticmethod
    def SaveToFile(file: str):
        config: dict[str, Any] = {}
        for arg in CLA.all_args:
            if arg.allow_saving:
                config[arg.arg.name] = arg.currentValue
        with open(file, "w") as the_file:
            the_file.write(json.dumps(config, indent="\t"))

    @staticmethod
    def getUsageStr(indent=2, forServerNotDownload=False):
        ret = ""
        for arg in CLA.all_args:
            noprefix = ""
            if arg.hidden and not CLA.getCommandLineArg(CommandLineArg.ADV_HELP):
                continue
            if CLA.getCommandLineArg(CommandLineArg.ADV_HELP) and not arg.hidden:
                continue
            if forServerNotDownload:
                if arg.applies_to == ArgAppliesTo.DOWNLOAD:
                    continue
            elif arg.applies_to == ArgAppliesTo.SERVING:
                continue

            desc = arg.description

            if arg.currentValue:
                if not arg.hasValue:
                    noprefix = "no-"
                    desc = f"disables: {desc}"
                else:
                    desc = f"{desc} currently: {arg.currentValue}"

            for _ in range(indent):
                ret += "\t"
            ret += f"--{noprefix}{arg.argConsoleName()} {arg.itemValueHelpDisplay} -- {desc}\n"
        return ret.rstrip()

    @staticmethod
    def getCommandLineArg(arg: CommandLineArg):
        if arg in CLA.value_cache:
            return CLA.value_cache[arg]
        cla = next(filter(lambda c: c.arg == arg, CLA.all_args), None)
        if not cla:
            raise Exception(f"Invalid command line arg requested???: {arg}")
        CLA.value_cache[arg] = cla.currentValue
        return cla.currentValue


DEFAULTS_JSON_FILE = "defaults.json"
if __name__ == "__main__":
    CLA.addCommandLineArg(CommandLineArg.BASE_FOLDER, "folder to store downloaded models in (or serve from)", "./downloads", itemValueHelpDisplay="dir", allow_saved=False, applies_to=ArgAppliesTo.BOTH)
    CLA.addCommandLineArg(CommandLineArg.BRUTE_JS, "downloading the range of matterports many JS files numbered 1->999.js, through trying them all rather than just the ones we know", False)
    CLA.addCommandLineArg(CommandLineArg.PROXY, "using web proxy specified for all requests", "", "127.0.0.1:8866", allow_saved=False)
    CLA.addCommandLineArg(CommandLineArg.TILDE, "allowing tildes on file paths, likely must be disabled for Apple/Linux, you must use the same option during the capture and serving", sys.platform == "win32")
    CLA.addCommandLineArg(CommandLineArg.ALIAS, "create an alias symlink for the download with this name, does not override any existing (can be used when serving)", "", itemValueHelpDisplay="name")
    CLA.addCommandLineArg(CommandLineArg.ADVANCED_DOWNLOAD, "downloading advanced assets enables things like skyboxes, dollhouse, floorplan layouts", True)
    CLA.addCommandLineArg(CommandLineArg.DEBUG, "debug mode enables select debug output to console or the debug/ folder mostly for developers", False, allow_saved=False)
    CLA.addCommandLineArg(CommandLineArg.CONSOLE_LOG, "showing all log messages in the console rather than just the log file, very spammy", False, allow_saved=False)

    CLA.addCommandLineArg(CommandLineArg.DOWNLOAD, "Download items (without this it just does post download actions)", True, hidden=True, allow_saved=False)
    CLA.addCommandLineArg(CommandLineArg.VERIFY_SSL, "SSL verification, mostly useful for proxy situations", True, allow_saved=False, hidden=True)
    CLA.addCommandLineArg(CommandLineArg.MAIN_ASSET_DOWNLOAD, "Primary asset downloads (normally biggest part of the download)", True, hidden=True, allow_saved=False)
    CLA.addCommandLineArg(CommandLineArg.ALWAYS_DOWNLOAD_GRAPH_REQS, "Always download/make graphql requests, a good idea as they have important keys", True, hidden=True, allow_saved=False)
    CLA.addCommandLineArg(CommandLineArg.MANUAL_HOST_REPLACEMENT, "Use old style replacement of matterport URLs rather than the JS proxy, this likely only works if hosted on port 8080 after", False, hidden=True)

    CLA.addCommandLineArg(CommandLineArg.QUIET, "Only show failure log message items when serving", False, applies_to=ArgAppliesTo.SERVING)
    CLA.addCommandLineArg(CommandLineArg.AUTO_SERVE, "Used to automatically start the server hosting a specific file, see README for details", "", "page_id_or_alias|host|port|what-browser", applies_to=ArgAppliesTo.SERVING, hidden=True)

    CLA.addCommandLineArg(CommandLineArg.HELP, "", False, hidden=True, allow_saved=False)
    CLA.addCommandLineArg(CommandLineArg.ADV_HELP, "Show advanced command line options normally hidden, not recommended for most users", False, hidden=False, allow_saved=False, applies_to=ArgAppliesTo.BOTH)
    CLA.parseArgs()
    browserLaunch = ""
    defaults_full_path = os.path.join(BASE_MATTERPORTDL_DIR, DEFAULTS_JSON_FILE)
    if os.path.exists(defaults_full_path):
        CLA.LoadFromFile(defaults_full_path)
        CLA.parseArgs()
        autoServe = CLA.getCommandLineArg(CommandLineArg.AUTO_SERVE)
        if autoServe:
            arr = autoServe.split("|")
            if len(arr) > 2:
                if len(arr) == 4:
                    browserLaunch = arr.pop()
                arr.insert(0, "matterport-dl.py")
                sys.argv = arr

    baseDir = CLA.getCommandLineArg(CommandLineArg.BASE_FOLDER)

    SetupSession(CLA.getCommandLineArg(CommandLineArg.PROXY))
    pageId = ""
    if len(sys.argv) > 1:
        pageId = getPageId(sys.argv[1])

    isServerRun = len(sys.argv) == 4
    if not os.path.exists(os.path.join(baseDir, pageId)) and os.path.exists(pageId) and isServerRun:  # allow old rooted pages to still be served
        baseDir = "./"
    else:
        makeDirs(baseDir)
        os.chdir(baseDir)

    existingConfigFile = os.path.join(pageId, RUN_ARGS_CONFIG_NAME)
    if os.path.exists(existingConfigFile):
        try:
            CLA.LoadFromFile(existingConfigFile)
            CLA.parseArgs()
        except:
            pass
    openDirReadGraphReqs(os.path.join(BASE_MATTERPORTDL_DIR, "graph_posts"), pageId)
    if len(sys.argv) == 2 and not CLA.getCommandLineArg(CommandLineArg.HELP) and not CLA.getCommandLineArg(CommandLineArg.ADV_HELP):
        asyncio.run(initiateDownload(pageId))

    elif len(sys.argv) == 4 and not CLA.getCommandLineArg(CommandLineArg.HELP) and not CLA.getCommandLineArg(CommandLineArg.ADV_HELP):
        try:
            logging.basicConfig(filename="server.log", filemode="w", encoding="utf-8", level=logging.DEBUG, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        except ValueError:
            logging.basicConfig(filename="server.log", filemode="w", level=logging.DEBUG, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

        twinDir = getPageId(pageId)
        if not os.path.exists(twinDir):
            fullPath = os.path.abspath(twinDir)
            relativeToScriptDir = os.path.join(BASE_MATTERPORTDL_DIR,baseDir,twinDir)
            if os.path.exists(relativeToScriptDir):
                os.chdir(relativeToScriptDir)
            else:
                raise Exception(f"Unable to change to download directory for twin of: {fullPath} or {os.path.abspath(relativeToScriptDir)} make sure the download is there")
        else:
            os.chdir(twinDir)
        logging.info(f"Server starting up {sys_info()}")
        url = "http://" + sys.argv[2] + ":" + sys.argv[3]
        print("View in browser: " + url)
        httpd = HTTPServer((sys.argv[2], int(sys.argv[3])), OurSimpleHTTPRequestHandler)
        if browserLaunch:
            print(f"Going to try and launch browser type: {browserLaunch}")
            import webbrowser
            if sys.platform == "win32":
                RegisterWindowsBrowsers()
            webbrowser.get(browserLaunch).open_new_tab(url)
        httpd.serve_forever()
    else:
        print("Usage:\n\tFirst download the digital twin: matterport-dl.py [url_or_page_id]\n\tThen launch the server 'matterport-dl.py [url_or_page_id_or_alias] 127.0.0.1 8080' and open http://127.0.0.1:8080 in a browser\n\tThe following options apply to the download run options:")
        print(CLA.getUsageStr())
        print("\tServing options:")
        print(CLA.getUsageStr(forServerNotDownload=True))
        print("\tAny option can have a no prefix added (or removed if already has) to invert the option,  ie --no-proxy disables a proxy if one was enabled.  --no-advanced-download disables the default enabled advanced download.")
