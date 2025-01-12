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
def delete (key):
  # getting current dictionary
  with open("converter.json", 'r') as pFile:
    file = pFile.readlines()
    obj = json.loads(file[0].split("\n")[0])
    obj.pop(key)
    file[0] = json.dumps(obj) + "\n"
  # writing new relation into the dictionary
  with open("converter.json", 'w') as pFile:
    pFile.writelines(file)
  print(f"{bcolors.BOLD}{bcolors.OKGREEN}matterport successfully deleted{bcolors.ENDC}")
def download(url):
  # getting website content and extracting matterport urls
  headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
  result = requests.get(url, headers=headers)
  content = result.content.decode()
  urls = set(re.findall(r'https://my\.matterport\.com/show/\?m=([a-zA-Z0-9]+)', content))
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
    subprocess.run(['python', 'matterport-dl.py', url])
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
  print(f'To {bcolors.BOLD}start{bcolors.ENDC} a matterport, please {bcolors.BOLD}enter the number{bcolors.ENDC} of the matterport in the list below. \nTo {bcolors.BOLD}download{bcolors.ENDC} a matterport, {bcolors.BOLD}enter the web adress{bcolors.ENDC} of it instead. If you would like to download {bcolors.BOLD}multiple matterports{bcolors.ENDC}, you can enter multiple web adresses {bcolors.BOLD}seperated by " "{bcolors.ENDC}\nTo {bcolors.BOLD}delete{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"delete "{bcolors.ENDC} followed by the associated number in the listed below.\nTo {bcolors.BOLD}rename{bcolors.ENDC} a matterport, enter {bcolors.BOLD}"rename "{bcolors.ENDC} followed by the associated number in the listed below.')
  keys = sorted(list(downloads.keys()))
  for i in range(len(keys)):
      print("[" + str(i + 1) + "] " + keys[i])
  print('-' * os.get_terminal_size().columns)
  answer = input("input: ")
  rm_index = re.findall(r'delete ([0-9]+)', answer)
  rn_index = re.findall(r'rename ([0-9]+)', answer)
  if answer.isnumeric():
    print("opening " + downloads[keys[int(answer) - 1]])
    subprocess.run(
    'python matterport-dl.py ' + downloads[keys[int(answer) - 1]] + ' 127.0.0.1 8080',
    shell=True
    )
  # deleting matterport
  elif len(rm_index) == 1:
      key = keys[int(rm_index[0])-1]
      path = get_absolute_path("downloads/" + downloads[key])
      shutil.rmtree(path)
      delete(key)
      initializing()
  # renaming matterport
  elif len(rn_index) == 1:
    key = keys[int(rn_index[0])-1]
    delete(key)
    save(input("please enter the new name for the matterport: "), downloads[key])
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}renaming successful{bcolors.ENDC}")
    initializing()
  else:
    for url in answer.split(" "):
      download(url)
    initializing()
initializing()