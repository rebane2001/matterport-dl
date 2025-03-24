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



DOWNLOAD_DIR="downloads"

def get_downloads_path():
    global DOWNLOAD_DIR
    return DOWNLOAD_DIR

def load_model_json(model_id):
    """Load JSON data from a model's run_args.json file, returning the data or an empty dictionary if not found"""
    run_args_path = os.path.join(get_downloads_path(), model_id, "run_args.json")
    if not os.path.exists(run_args_path):
        print_colored(f"Warning: No run_args.json found for {model_id}", bcolors.WARNING)
        return {}
    try:
        with open(run_args_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print_colored(f"Error: Invalid JSON in run_args.json for model {model_id}", bcolors.WARNING)
        return {}
    except FileNotFoundError:
        print_colored(f"Warning: No run_args.json found for {model_id}", bcolors.WARNING)
        return {}
    except Exception as e:
        print_colored(f"Error reading run_args.json for model {model_id}: {str(e)}", bcolors.WARNING)
        return {}


def save_model_json(model_id, data):
    """Save JSON data to a model's run_args.json file, returning True if successful, False otherwise"""
    run_args_path = os.path.join(get_downloads_path(), model_id, "run_args.json")
    try:
        with open(run_args_path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print_colored(f"Error saving run_args.json for model {model_id}: {str(e)}", bcolors.WARNING)
        return False


def load_model_data():
    """Load all model data from run_args.json files in download directories, returning a dictionary of the model id to name/alias/title"""
    models = {}
    downloads_path = get_downloads_path()
    if not os.path.exists(downloads_path):
        os.makedirs(downloads_path)
        return models

    for model_id in os.listdir(downloads_path):
        model_path = os.path.join(downloads_path, model_id)
        if not os.path.isdir(model_path) or os.path.islink(model_path):
            continue

        data = load_model_json(model_id)
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
    return models


def remove_alias_smylink(expected_owner_model_id, alias):
    """Checks if in the downloads folder there is a sym link and pointing to expected_owner_model_id if so remove it otherwise we do nothing"""
    downloads_path = get_downloads_path()
    alias_path = os.path.join(downloads_path, alias)
    if os.path.islink(alias_path):
        target = os.readlink(alias_path)
        if expected_owner_model_id.lower() in target.lower():
            try:
                os.remove(alias_path)
                print_colored("Removed old alias symlink", bcolors.OKGREEN)
            except OSError as e:
                print_colored(f"Error removing symlink {alias}: {e}", bcolors.WARNING)


def create_alias_smylink(model_id, alias):
    """Create a symlink in the downloads folder pointing to the model_id"""
    downloads_path = get_downloads_path()
    alias_path = os.path.join(downloads_path, alias)
    model_path = os.path.join(downloads_path, model_id)
    if not os.path.exists(alias_path):
        try:
            os.symlink(model_path, alias_path)
            print_colored(f"Created symlink {alias} pointing to {model_id}", bcolors.OKGREEN)
        except OSError as e:
            print_colored(f"Error creating symlink alias {alias}: {e}", bcolors.WARNING)


def update_model_alias(model_id, new_title):
    """Update the title in run_args.json and create a symlink with the new title"""
    data = load_model_json(model_id)
    old_title = data.get("ALIAS", "")
    if old_title:
        remove_alias_smylink(model_id, old_title)
    data["ALIAS"] = new_title
    if save_model_json(model_id, data):
        create_alias_smylink(model_id, new_title)
        return True
    return False


def print_separator():
    print("-" * os.get_terminal_size().columns)


def print_colored(message, color, bold=True):
    prefix = f"{bcolors.BOLD}" if bold else ""
    print(f"{prefix}{color}{message}{bcolors.ENDC}")


def error_message(msg):
    print_colored(msg, bcolors.FAIL)


class bcolors:
    COLORS = {
        "HEADER": "95",
        "OKBLUE": "94",
        "OKCYAN": "96",
        "OKGREEN": "92",
        "WARNING": "93",
        "FAIL": "91",
        "UNINMPORTANT": "2",
        "ENDC": "0",
        "BOLD": "1",
    }

    def __init__(self):
        # Dynamically create color attributes
        for name, code in self.COLORS.items():
            setattr(self, name, f"\033[{code}m")


bcolors = bcolors()  # Initialize once

COMMANDS = {"delete": ["del", "rm", "delete"], "rename": ["re", "ren", "rename"], "download": ["dl", "download"]}


def parse_command(answer):
    """Parse user input into command and argument"""
    answer = answer.strip()
    for cmd_type, aliases in COMMANDS.items():
        for alias in aliases:
            if answer.lower().startswith(f"{alias} "):
                return cmd_type, answer[len(alias) :].strip()
    return None, answer


def download(matterportArgs, url):
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
        fullArgs = [sys.executable] + matterportArgs + [url]
        output = subprocess.run(fullArgs)
        if output.returncode == 1:
            print_colored('Download failed! Make sure you type in a valid web address or ID. The web address must contain "https://" Please consider that the downloader itself might be broken.', bcolors.FAIL)
        print_separator()


def getModelId(input_text, keys, downloads):
    """Get a key from user input, either by index or name prefix"""
    if not input_text:
        return None

    # Try index first
    try:
        match = keys[int(input_text) - 1]
        print(f"Selecting {match} ({downloads[match]})")
        return match
    except (ValueError, IndexError):
        pass

    # Try direct key match
    matches = [k for k in keys if k.lower().startswith(input_text.lower())]
    if matches:
        match = matches[0]
        print(f"Selecting {match} ({downloads[match]})")
        return match

    # Try alias/title match against the start of the string
    for key in keys:
        if downloads[key].lower().startswith(input_text.lower()):
            print(f"Selecting {key} ({downloads[key]})")
            return key

    return None


def handle_model_not_found():
    """Handle case when no matching model is found"""
    error_message("No matching matterport found. Please try again, to download a model use 'download [url|model_id]'.")
    return False


def interactiveManagerGetToServe(downloadDir, matterportArgs):
    """Allows the user to interactively select a matterport to serve, download, rename, or delete.  If the user wants to serve then this function returns the model id to serve"""
    global WORDS, DOWNLOAD_DIR
    DOWNLOAD_DIR = downloadDir
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")

    while True:
        print_separator()
        downloads = load_model_data()

        print(f"To start/serve a matterport, please {bcolors.BOLD}enter the number or the name{bcolors.ENDC} of the matterport in the list below.")
        print(f'To {bcolors.BOLD}download{bcolors.ENDC} a matterport, {bcolors.BOLD}enter "download "{bcolors.ENDC} followed by the web address or ID{bcolors.ENDC}')
        print(f'To download {bcolors.BOLD}multiple matterports{bcolors.ENDC}, you can enter multiple web addresses {bcolors.BOLD}separated by " "{bcolors.ENDC}')
        print(f'To {bcolors.BOLD}delete{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"delete "{bcolors.ENDC} followed by the associated number or name.')
        print(f'To {bcolors.BOLD}rename{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"rename "{bcolors.ENDC} followed by the associated number or name.')
        print(f"You can press {bcolors.BOLD}tab{bcolors.ENDC} to {bcolors.BOLD}auto-complete{bcolors.ENDC} names of the matterport.")

        WORDS = [f"{cmd} " for cmds in COMMANDS.values() for cmd in cmds]
        keys = sorted(list(downloads.keys()), key=lambda k: downloads[k].lower())

        for i, key in enumerate(keys, 1):
            itemName = key
            WORDS.append(key)
            if downloads[key]:
                WORDS.append(downloads[key])
                itemName = f"{downloads[key]} ({itemName})"
            print(f"[{i}] {itemName}")

        print(f"{bcolors.BOLD}Ctrl-C{bcolors.ENDC} to {bcolors.BOLD}exit{bcolors.ENDC}.")

        print_separator()
        try:
            answer = input("input: ")
        except EOFError or KeyboardInterrupt:  # ^C or ^D to exit (POSIX-based), actually keyboard interrupt wont be raised by our default signal handler
            print()
            sys.exit(130)
        command, arg = parse_command(answer)

        if command == "delete":
            model_id = getModelId(arg, keys, downloads)
            if not model_id:
                handle_model_not_found()
                continue

            prompt = f'please enter {bcolors.BOLD}"{model_id}"{bcolors.ENDC} or the title {bcolors.BOLD}"{downloads[model_id]}"{bcolors.ENDC} to confirm the {bcolors.BOLD}{bcolors.FAIL}deletion{bcolors.ENDC} of the matterport: '
            while True:
                pInput = input(prompt)
                if pInput in [downloads[model_id], model_id, "cancel"]:
                    break
                error_message("You did not enter the right name or ID.")
                prompt = f'Please try again (enter {bcolors.BOLD}"{model_id}"{bcolors.ENDC} or {bcolors.BOLD}"{downloads[model_id]}"{bcolors.ENDC}) or enter {bcolors.BOLD}"cancel"{bcolors.ENDC} to cancel the {bcolors.FAIL}{bcolors.BOLD}deletion: {bcolors.ENDC}'

            if pInput != "cancel":
                path = os.path.join(get_downloads_path(), model_id)
                model_data = load_model_json(model_id)
                if model_data.get("ALIAS"):
                    remove_alias_smylink(model_id, model_data["ALIAS"])

                shutil.rmtree(path)
                print_colored("matterport successfully deleted", bcolors.OKGREEN)

        elif command == "rename":
            model_id = getModelId(arg, keys, downloads)
            if not model_id:
                handle_model_not_found()
                continue

            new_name = input("please enter the new name for the matterport: ")
            if update_model_alias(model_id, new_name):
                print_colored("renaming successful", bcolors.OKGREEN)
            else:
                error_message("failed to rename matterport")

        elif command == "download":
            for url in arg.split(" "):
                download(matterportArgs, url)
        else:  # assume user wants to start/serve it so just make sure it exists
            model_id = getModelId(arg, keys, downloads)
            if not model_id:
                handle_model_not_found()
                continue
            if model_id:
                return model_id


def find_matches(text, items):
    """Find items that start with the given text (case insensitive)"""
    return [item for item in items if item.lower().startswith(text.lower())]


def completer(text, state):
    matches = find_matches(text, WORDS)
    return matches[state] if state < len(matches) else None


WORDS = []
