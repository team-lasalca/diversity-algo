import json
import sys

#FIRST = "phystech-master/example/model_output.json"
#SECOND = "phystech-master/example/output.json"

FIRST = sys.argv[1]
SECOND = sys.argv[2]

with open(FIRST, "r") as file:
    first = json.load(file)
with open(SECOND, "r") as file:
    second = json.load(file)

with open(FIRST, "w") as file:
    file.write(json.dumps([*first, *second]))

print("Saved.")