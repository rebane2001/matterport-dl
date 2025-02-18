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


def get_downloads_path():
    return get_absolute_path("downloads")


def load_model_data():
    """Load all model data from run_args.json files in download directories"""
    models = {}
    downloads_path = get_downloads_path()
    if not os.path.exists(downloads_path):
        os.makedirs(downloads_path)
        return models

    for model_id in os.listdir(downloads_path):
        model_path = os.path.join(downloads_path, model_id)
        if not os.path.isdir(model_path) or os.path.islink(model_path):
            continue

        run_args_path = os.path.join(model_path, "run_args.json")
        if not os.path.exists(run_args_path):
            print_colored(f"Warning: No run_args.json found for {model_id}", bcolors.WARNING)
            # Still include the model using ID as name
            models[model_id] = model_id
            continue

        try:
            with open(run_args_path, "r") as f:
                data = json.load(f)
                name = ""
                if data.get("ALIAS"):
                    name = data.get("ALIAS")
                if data.get("TITLE"):
                    if name:
                        name += " - "
                    name += data.get("TITLE")
                # If no name was found, use the model ID
                if not name:
                    name = model_id
                models[model_id] = name
        except json.JSONDecodeError:
            print_colored(f"Error: Invalid JSON in run_args.json for {model_id}", bcolors.WARNING)
            models[model_id] = model_id
        except Exception as e:
            print_colored(f"Error reading run_args.json for {model_id}: {str(e)}", bcolors.WARNING)
            models[model_id] = model_id
    return models


def update_model_alias(model_id, new_title):
    """Update the title in run_args.json"""
    run_args_path = os.path.join(get_downloads_path(), model_id, "run_args.json")
    if os.path.exists(run_args_path):
        try:
            with open(run_args_path, "r") as f:
                data = json.load(f)
            data["ALIAS"] = new_title
            with open(run_args_path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except:
            print_colored(f"Error updating run_args.json for {model_id}", bcolors.WARNING)
            return False
    return False


def print_colored(message, color, bold=True):
    prefix = f"{bcolors.BOLD}" if bold else ""
    print(f"{prefix}{color}{message}{bcolors.ENDC}")


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
        output = subprocess.run([sys.executable, "matterport-dl.py", url])
        if output.returncode == 1:
            print_colored('Download failed! Make sure you type in a valid web address or ID. The web address must contain "https://" Please consider that the downloader itself might be broken.', bcolors.FAIL)
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


def parse_command(answer):
    """Parse user input into command and argument"""
    commands = {"delete": ["del", "rm", "delete"], "rename": ["rename", "re", "ren"], "download": ["dl", "download"]}

    answer = answer.strip()
    for cmd_type, aliases in commands.items():
        for alias in aliases:
            if answer.lower().startswith(f"{alias} "):
                return cmd_type, answer[len(alias) :].strip()
    return None, answer


def initializing():
    global WORDS
    print("-" * os.get_terminal_size().columns)
    downloads = load_model_data()

    print(f"To {bcolors.BOLD}start{bcolors.ENDC} a matterport, please {bcolors.BOLD}enter the number or the name{bcolors.ENDC} of the matterport in the list below.")
    print(f'To {bcolors.BOLD}download{bcolors.ENDC} a matterport, {bcolors.BOLD}enter "download "{bcolors.ENDC} followed by the web address or ID{bcolors.ENDC}')
    print(f'To download {bcolors.BOLD}multiple matterports{bcolors.ENDC}, you can enter multiple web addresses {bcolors.BOLD}separated by " "{bcolors.ENDC}')
    print(f'To {bcolors.BOLD}delete{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"delete "{bcolors.ENDC} followed by the associated number or name.')
    print(f'To {bcolors.BOLD}rename{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"rename "{bcolors.ENDC} followed by the associated number or name.')
    print(f"You can press {bcolors.BOLD}tab{bcolors.ENDC} to {bcolors.BOLD}auto-complete{bcolors.ENDC} names of the matterport.")

    WORDS = list(["delete ", "rename ", "download "])
    keys = sorted(list(downloads.keys()))
    for i, key in enumerate(keys, 1):
        itemName = key
        WORDS.append(key)
        if downloads[key]:
            WORDS.append(downloads[key])
            itemName = f"{downloads[key]} ({itemName})"
        print(f"[{i}] {itemName}")
    print("-" * os.get_terminal_size().columns)

    answer = input("input: ")

    command, arg = parse_command(answer)

    if command == "delete":
        model_id = getModelId(arg, keys, downloads)
        if not model_id:
            print_colored("No matching matterport found. Please try again.", bcolors.FAIL)
            initializing()
            return
        pInput = input(f'please enter {bcolors.BOLD}"{model_id}"{bcolors.ENDC} or the title {bcolors.BOLD}"{downloads[model_id]}"{bcolors.ENDC} to confirm the {bcolors.BOLD}{bcolors.FAIL}deletion{bcolors.ENDC} of the matterport: ')
        while not (pInput in [downloads[model_id], model_id] or pInput == "cancel"):
            print_colored("You did not enter the right name or ID.", bcolors.FAIL)
            pInput = input(f'Please try again (enter {bcolors.BOLD}"{model_id}"{bcolors.ENDC} or {bcolors.BOLD}"{downloads[model_id]}"{bcolors.ENDC}) or enter {bcolors.BOLD}"cancel"{bcolors.ENDC} to cancel the {bcolors.FAIL}{bcolors.BOLD}deletion: {bcolors.ENDC}')
        if pInput != "cancel":
            path = os.path.join(get_downloads_path(), model_id)
            shutil.rmtree(path)
            print_colored("matterport successfully deleted", bcolors.OKGREEN)
    elif command == "rename":
        model_id = getModelId(arg, keys, downloads)
        if not model_id:
            print_colored("No matching matterport found. Please try again.", bcolors.FAIL)
            initializing()
            return
        new_name = input("please enter the new name for the matterport: ")
        if update_model_alias(model_id, new_name):
            print_colored("renaming successful", bcolors.OKGREEN)
        else:
            print_colored("failed to rename matterport", bcolors.FAIL)
    elif command == "download":
        for url in arg.split(" "):
            download(url)
    else:
        model_id = getModelId(arg, keys, downloads)
        if model_id:
            print(f"opening {model_id}")
            subprocess.run([sys.executable, "matterport-dl.py", model_id, "127.0.0.1", "8080"])
        else:
            print_colored("Model not found or invalid command. To download, use 'download' followed by the URL or ID. To open a matterport, enter its number or name.", bcolors.FAIL)

    initializing()


def find_matches(text, items):
    """Find items that start with the given text (case insensitive)"""
    return [item for item in items if item.lower().startswith(text.lower())]


def getModelId(input, keys, downloads):
    """Get a key from user input, either by index or name prefix match"""

    try:
        match = keys[int(input) - 1]
    except (ValueError, IndexError):
        matches = find_matches(input, keys)
        if matches:
            match = matches[0]
        else:
            for key in keys:
                if downloads[key].lower().startswith(input.lower()):
                    match = key
                    break
    if not match:
        return None
    print(f"Selecting {match} ({downloads[match]})")
    return match


def completer(text, state):
    matches = find_matches(text, WORDS)
    return matches[state] if state < len(matches) else None


WORDS = []
readline.set_completer(completer)
readline.parse_and_bind("tab: complete")

initializing()
