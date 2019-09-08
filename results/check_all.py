import subprocess
from glob import glob

for file in glob("../cluster_results/*"):
    command = ["python3", "check.py", "../phystech-master/data/contest_input.json", file]
    try:
        tmp = subprocess.check_output(command)
    except:
        print(file)
