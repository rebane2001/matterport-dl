import subprocess
import requests
import re
import json
import shutil
import os

def get_absolute_path(relative_path):
  # Get the absolute path of the current script
  script_directory = os.path.dirname(os.path.abspath(__file__))
  # Combine the script's directory with the relative path
  return os.path.join(script_directory, relative_path)

# saving the relation between the URL/matterport-ID (value) and the entered name (key)
def save (key, value):
  # getting current dictionary
  with open("converter.json", 'r') as pFile:
    file = pFile.readlines()
    obj = json.loads(file[0].split("\n")[0])
    obj[key] = value
    file[0] = json.dumps(obj) + "\n"
  # writing new relation into the dictionary
  with open("converter.json", 'w') as pFile:
    pFile.writelines(file)
def delete (key, alert=True):
  # getting current dictionary
  with open("converter.json", 'r') as pFile:
    file = pFile.readlines()
    obj = json.loads(file[0].split("\n")[0])
    obj.pop(key)
    file[0] = json.dumps(obj) + "\n"
  # writing new relation into the dictionary
  with open("converter.json", 'w') as pFile:
    pFile.writelines(file)
  if alert:
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}matterport successfully deleted{bcolors.ENDC}")
def download(url):
  # getting website content and extracting matterport urls
  headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
  result = requests.get(url, headers=headers)
  content = result.content.decode()
  urls = set(re.findall(r'https://my\.matterport\.com/show/\?m=([a-zA-Z0-9]+)', content))
  # TODO: support more website types?: https://my.matterport.com/models/EGxFGTFyC9N
  # https://my.matterport.com/work?m=EGxFGTFyC9N
  # urls = set(re.findall(r'https://my\.matterport\.com/(show/|work)\?m=([a-zA-Z0-9]+)', content))
  if len(urls) < 1:
    download(input("no matterport was found! please enter a valid web adress: "))
    return
  for url in urls:
    # abstracting the matterport name
    result = requests.get("https://my.matterport.com/show?m=" + url, headers=headers)
    content = result.content.decode()
    name = re.findall(r'<title>(.*) - Matterport 3D Showcase</title>', content)[0]
    if name == None or len(name) == 0:
      name = input("please give the matterport a name: ")
    # initiating the download
    subprocess.run(['python3', 'matterport-dl.py', url])
    save(name, url)
    # print(f"{bcolors.BOLD}{bcolors.OKGREEN}matterport {name} downloaded successfully{bcolors.ENDC}")

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# "starting screen" of the program
def initializing():
  print('-' * os.get_terminal_size().columns)
  # loading the name to ID converter
  with open("converter.json", 'r') as pFile:
    file = pFile.readlines()
    downloads = json.loads(file[0].split("\n")[0])
  # downloads = {"Stiftung Museum der belgischen Streitkräfte Deutschlands": "NwnPwA7ppRc", "Burghofmuseum": "5H92DDxwJK8", "Osthofentormuseum": "LejqidHAk6q", "Sankt Maria zur Wiese": "C3eLgupYBMm", "Sankt Maria zur Höhe": "8zTg44vs7L1", "Petrikirche Soest": "AW4kxBZ4wAm", "Grünsandsteinmuseum Soest": "qP8dUoSBk3R", "Brunsteinkapelle Soest": "aJhHnHiGp1s", "Der Bunker in Soest 2020: LIEBES LEBEN MUSEUM": "EUQnCirRNGp", "Museum Wilhelm Morgner": "gDFTCKQoFPQ"}
  print(f'To {bcolors.BOLD}start{bcolors.ENDC} a matterport, please {bcolors.BOLD}enter the number or the name{bcolors.ENDC} of the matterport in the list below. \nTo {bcolors.BOLD}download{bcolors.ENDC} a matterport, {bcolors.BOLD}enter the web adress{bcolors.ENDC} of it instead. If you would like to download {bcolors.BOLD}multiple matterports{bcolors.ENDC}, you can enter multiple web adresses {bcolors.BOLD}seperated by " "{bcolors.ENDC}\nTo {bcolors.BOLD}delete{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"delete "{bcolors.ENDC} followed by the associated number or the name of the matterport in the listed below.\nTo {bcolors.BOLD}rename{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"rename "{bcolors.ENDC} followed by the associated number or the name of the matterport in the listed below.\nYou can press {bcolors.BOLD}tab{bcolors.ENDC} to {bcolors.BOLD}auto-complete{bcolors.ENDC} names of the matterport. ')
  keys = sorted(list(downloads.keys()))
  for i in range(len(keys)):
      print("[" + str(i + 1) + "] " + keys[i])
  print('-' * os.get_terminal_size().columns)
  global WORDS
  WORDS = [*keys, *["delete ", "rename "]]
  answer = input("input: ")
  rm_index = re.findall(r'delete (.*)', answer)
  rn_index = re.findall(r'rename (.*)', answer)
  if answer.isnumeric() or answer in keys:
    if answer in keys:
      answer = keys.index(answer) + 1
    elif not answer in range(0, len(downloads)):
      print(f"{bcolors.BOLD}{bcolors.FAIL}please enter a number form 0 to {len(downloads)} to open the associated matterport{bcolors.ENDC}")
      initializing()
    print("opening " + downloads[keys[int(answer) - 1]])
    subprocess.run(
    'python3 matterport-dl.py ' + downloads[keys[int(answer) - 1]] + ' 127.0.0.1 8080',
    shell=True
    )
  # deleting matterport
  elif len(rm_index) == 1:
    key = getKey(rm_index[0], keys)
    pInput = input(f'please enter {bcolors.BOLD}"{key}"{bcolors.ENDC} or the ID {bcolors.BOLD}"{downloads[key]}"{bcolors.ENDC} to confirm the {bcolors.BOLD}{bcolors.FAIL}deletion{bcolors.ENDC} of the matterport: ')
    while not (pInput in [key, downloads[key]] or pInput == "cancel"):
      print(f'{bcolors.BOLD}{bcolors.FAIL}You did not enter the right name or ID. {bcolors.ENDC}')
      pInput = input(f'Please try again (enter {bcolors.BOLD}"{key}"{bcolors.ENDC} or {bcolors.BOLD}"{downloads[key]}"{bcolors.ENDC}) or enter {bcolors.BOLD}"cancel"{bcolors.ENDC} to cancel the {bcolors.FAIL}{bcolors.BOLD}deletion: {bcolors.ENDC}')
    if pInput != "cancel":
      path = get_absolute_path("downloads/" + downloads[key])
      shutil.rmtree(path)
      delete(key)
    initializing()
  # renaming matterport
  elif len(rn_index) == 1:
    key = getKey(rn_index[0], keys)
    save(input("please enter the new name for the matterport: "), downloads[key])
    delete(key, alert=False)
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}renaming successful{bcolors.ENDC}")
    initializing()
  else:
    for url in answer.split(" "):
      download(url)
    initializing()

# gets matterport name by ID or name and returns the name
def getKey(input, keys):
  try:
    key = keys[int(input)-1]
  except ValueError:
    if input in keys:
      key = input
    else:
      print(f'{bcolors.BOLD}{bcolors.FAIL}You did not type the name of the matterport correctly. Please try again.{bcolors.ENDC}')
      initializing()
  return key

# tab autocomplete
import readline
WORDS = ["delete ", "rename"]
def completer(text, state):
    # Build a list of matching words
    matches = [word for word in WORDS if word.lower().startswith(text.lower())]
    try:
        return matches[state]
    except IndexError:
        return None

# Set our completer function and bind the Tab key for completion.
readline.set_completer(completer)
readline.parse_and_bind("tab: complete")

initializing()