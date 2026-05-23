#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export PYTHONPATH=src

python3 -m unittest discover -s tests
python3 eval/run_eval.py
python3 -m compileall -q src tests eval
node --check web/static/app.js

python3 - <<'PY'
from proofmark.roadmap import build_track_b_plan

payload = {
    "learning_objective": "Explain Linux containers, namespaces, cgroups, and container isolation.",
    "content_set": [
        {
            "type": "notes",
            "title": "Linux container note",
            "text": (
                "Linux containers isolate processes using namespaces for PID, network, mount, IPC, and users. "
                "Cgroups limit CPU, memory, and IO usage for a group of processes. "
                "Container images are built from read-only layers plus a writable container layer."
            ),
        }
    ],
}
result = build_track_b_plan(payload)
concepts = [item["name"] for item in result["content_graph"]["concepts"][:4]]
assert concepts[:3] == ["Linux containers", "Namespaces", "Cgroups"], concepts
assert result["dynamic_case"]["grounding"]["source_claims"], "missing source claims"
print("smoke: ok")
PY
