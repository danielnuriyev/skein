import os
import re

K8S_DIR = "k8s"

files = [
    "slack-server-deployment.yaml",
    "slack-events-deployment.yaml",
    "github-pr-reviewer-deployment.yaml",
    "goose-server-deployment.yaml"
]

for filename in files:
    path = os.path.join(K8S_DIR, filename)
    if not os.path.exists(path):
        print(f"Skipping {filename}")
        continue
        
    with open(path, "r") as f:
        lines = f.readlines()

    new_lines = []
    skip = False
    skip_indent = 0

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        
        if skip:
            if stripped == "" or indent > skip_indent or stripped.startswith("-"):
                continue
            else:
                skip = False

        if stripped.startswith("image: python:3.12-slim"):
            new_lines.append(line.replace("image: python:3.12-slim", "image: goose-app:latest"))
            new_lines.append(line[:indent] + "imagePullPolicy: Never\n")
            continue
            
        if stripped == "volumeMounts:" or stripped == "volumes:":
            skip = True
            skip_indent = indent
            continue
            
        new_lines.append(line)

    with open(path, "w") as f:
        f.writelines(new_lines)
    print(f"Patched {filename}")

deploy_script = "scripts/deploy-k8s.sh"
with open(deploy_script, "r") as f:
    deploy_content = f.read()

deploy_content = deploy_content.replace(
    'apply_manifest "${K8S_DIR}/goose-configmaps.yaml" "Goose config maps"',
    '# apply_manifest "${K8S_DIR}/goose-configmaps.yaml" "Goose config maps"'
)

with open(deploy_script, "w") as f:
    f.write(deploy_content)
print("Patched deploy script")
