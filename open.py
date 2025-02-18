#!/usr/bin/env python3

# ruff: noqa: E722
import subprocess
import requests
import re
import json
import shutil
import os
import sys
import readline


def get_absolute_path(relative_path):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_directory, relative_path)


def load_converter_json():
    with open("converter.json", "r") as pFile:
        return json.loads(pFile.readline().strip())


def save_converter_json(data):
    with open("converter.json", "w") as pFile:
        pFile.write(json.dumps(data) + "\n")


def print_colored(message, color, bold=True):
    prefix = f"{bcolors.BOLD}" if bold else ""
    print(f"{prefix}{color}{message}{bcolors.ENDC}")


def save(key, value):
    data = load_converter_json()
    data[key] = value
    save_converter_json(data)


def delete(key, alert=True):
    data = load_converter_json()
    data.pop(key)
    save_converter_json(data)
    if alert:
        print_colored("matterport successfully deleted", bcolors.OKGREEN)


def download(url):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36"}

    if "https://" in url:
        result = requests.get(url, headers=headers)
        content = result.content.decode()
        urls = set(re.findall(r"https://my\.matterport\.com/show/\?m=([a-zA-Z0-9]+)", content))
        # TODO: support more website types?: https://my.matterport.com/models/EGxFGTFyC9N
        # https://my.matterport.com/work?m=EGxFGTFyC9N
        # urls = set(re.findall(r'https://my\.matterport\.com/(show/|work)\?m=([a-zA-Z0-9]+)', content))
        if len(urls) < 1:
            download(input("no matterport was found! please enter a valid web address: "))
            return
    else:
        urls = [url]

    for url in urls:
        result = requests.get("https://my.matterport.com/show?m=" + url, headers=headers)
        content = result.content.decode()
        try:
            name = re.findall(r"<title>(.*) - Matterport 3D Showcase</title>", content)[0]
        except IndexError:
            name = None

        if not name:
            name = input("please give the matterport a name: ")

        output = subprocess.run([sys.executable, "matterport-dl.py", url])
        if output.returncode == 1:
            print_colored('Download failed! Make sure you type in a valid web address or ID. The web address must contain "https://" Please consider that the downloader itself might be broken.', bcolors.FAIL)
        else:
            save(name, url)
        print("-" * os.get_terminal_size().columns)


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    UNINMPORTANT = "\033[2m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def initializing():
    print("-" * os.get_terminal_size().columns)
    downloads = load_converter_json()

    print(f"To {bcolors.BOLD}start{bcolors.ENDC} a matterport, please {bcolors.BOLD}enter the number or the name{bcolors.ENDC} of the matterport in the list below.")
    print(f'To {bcolors.BOLD}download{bcolors.ENDC} a matterport, {bcolors.BOLD}enter {bcolors.BOLD}"download "{bcolors.ENDC} the web address or ID{bcolors.ENDC}')
    print(f'\tTo download {bcolors.BOLD}multiple matterports{bcolors.ENDC}, you can enter multiple web addresses {bcolors.BOLD}separated by " "{bcolors.ENDC}')
    print(f'To {bcolors.BOLD}delete{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"delete "{bcolors.ENDC} followed by the associated number or name.')
    print(f'To {bcolors.BOLD}rename{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"rename "{bcolors.ENDC} followed by the associated number or name.')
    print(f"You can press {bcolors.BOLD}tab{bcolors.ENDC} to {bcolors.BOLD}auto-complete{bcolors.ENDC} names of the matterport.")

    keys = sorted(list(downloads.keys()))
    for i, key in enumerate(keys, 1):
        print(f"[{i}] {key}")
    print("-" * os.get_terminal_size().columns)

    global WORDS
    WORDS = [*keys, *["delete ", "rename ", "download "]]
    answer = input("input: ")

    rm_index = re.findall(r"(?:del|rm|delete) (.*)", answer)
    rn_index = re.findall(r"(?:rename|re|ren) (.*)", answer)
    dl_match = re.findall(r"(?:dl|download) (.*)", answer)

    if answer.isnumeric():
        if int(answer) not in range(1, len(downloads) + 1):
            print_colored(f"please enter a number from 1 to {len(downloads)} to open the associated matterport", bcolors.FAIL)
            initializing()
            return
        key = keys[int(answer) - 1]
        print("opening " + downloads[key])
        subprocess.run([sys.executable, "matterport-dl.py", downloads[key], "127.0.0.1", "8080"])
    elif len(rm_index) == 1:
        key = getKey(rm_index[0], keys)
        pInput = input(f'please enter {bcolors.BOLD}"{key}"{bcolors.ENDC} or the ID {bcolors.BOLD}"{downloads[key]}"{bcolors.ENDC} to confirm the {bcolors.BOLD}{bcolors.FAIL}deletion{bcolors.ENDC} of the matterport: ')
        while not (pInput in [key, downloads[key]] or pInput == "cancel"):
            print_colored("You did not enter the right name or ID.", bcolors.FAIL)
            pInput = input(f'Please try again (enter {bcolors.BOLD}"{key}"{bcolors.ENDC} or {bcolors.BOLD}"{downloads[key]}"{bcolors.ENDC}) or enter {bcolors.BOLD}"cancel"{bcolors.ENDC} to cancel the {bcolors.FAIL}{bcolors.BOLD}deletion: {bcolors.ENDC}')
        if pInput != "cancel":
            path = get_absolute_path("downloads/" + downloads[key])
            shutil.rmtree(path)
            delete(key)
    elif len(rn_index) == 1:
        key = getKey(rn_index[0], keys)
        new_name = input("please enter the new name for the matterport: ")
        save(new_name, downloads[key])
        delete(key, alert=False)
        print_colored("renaming successful", bcolors.OKGREEN)
    elif len(dl_match) == 1:
        for url in dl_match[0].split(" "):
            download(url)
    else:
        matches = [key for key in keys if key.lower().startswith(answer.lower())]
        if matches:
            key = matches[0]
            print("opening " + downloads[key])
            subprocess.run([sys.executable, "matterport-dl.py", downloads[key], "127.0.0.1", "8080"])
        else:
            print_colored("Model not found or invalid command. To download, use 'dl' followed by the URL or ID. To open a matterport, enter its number or name.", bcolors.FAIL)

    initializing()


def find_matches(text, items):
    """Find items that start with the given text (case insensitive)"""
    return [item for item in items if item.lower().startswith(text.lower())]

def getKey(input, keys):
    match=""
    try:
        match = keys[int(input) - 1]
    except ValueError:
        matches = find_matches(input, keys)
        if matches:
            match = matches[0]
        else:
            print_colored("No matching matterport found. Please try again.", bcolors.FAIL)
            initializing()
    print_colored(f"Selecting match: {match}", bcolors.UNINMPORTANT)
    return match

def completer(text, state):
    matches = find_matches(text, WORDS)
    return matches[state] if state < len(matches) else None


WORDS = []
readline.set_completer(completer)
readline.parse_and_bind("tab: complete")

initializing()
