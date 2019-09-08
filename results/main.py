import subprocess
import os
from glob import glob

child_processes = []
for i, file in enumerate(glob("../cluster/*")):
    print(file)

    command = ["python3", "or_tools.py", file, "../cluster_results/" + str(i) + ".json"]
    print(command)
    p = subprocess.Popen(command)
    child_processes.append(p)
    #subprocess.run(command)

for cp in child_processes:
    cp.wait()

first = glob("../cluster_results/*")[0]
print(first)

for file in glob("../cluster_results/*"):
    if file == first:
        continue
    
    command = ["python3", "join_json.py", first, file]
    print(command)
    subprocess.run(command)

    #os.remove(file)

subprocess.run(["python3", "check.py", "../phystech-master/data/contest_input.json", first])