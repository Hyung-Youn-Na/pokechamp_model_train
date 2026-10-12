"""Build and verify the pinned official client without upstream update scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).parent
DEFAULT_BUILD = ROOT / ".artifacts/official-observation/v1"
CLIENT = ROOT / ".artifacts/ep055/client"
SERVER = ROOT / "pokemon-showdown"
PIN = "f2faebd6892b314d785a0038f77309afed36970c"
SERVER_PIN = "e64915c0eab066db1d3e732b1280386468dd7415"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory):
    return {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob("*"))
            if p.is_file() and not p.is_symlink()}


def revision(directory):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=directory, text=True).strip()


def create(output):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["node", str(MODULE / "client.cjs"), "build", str(CLIENT), str(SERVER),
                    str(output)], check=True)
    provenance = json.loads((output / "provenance.json").read_text())
    if provenance["client_commit"] != PIN or provenance["server_commit"] != SERVER_PIN:
        raise ValueError("unexpected official source revision")
    manifest = dict(client_commit=PIN, server_commit=SERVER_PIN,
                    client_js_sha256=sha(output / "client.js"),
                    data_sha256=sha(output / "dex.json"),
                    provenance_sha256=sha(output / "provenance.json"),
                    dependencies=inventory(CLIENT / "node_modules"),
                    server_dist=inventory(SERVER / "dist"))
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return {"version": "official-client-v1", "client_commit": PIN,
            "server_commit": SERVER_PIN, "manifest_sha256": sha(output / "manifest.json")}


def verify(directory=DEFAULT_BUILD):
    directory = Path(directory).resolve()
    expected = json.loads((MODULE / "build-identity.json").read_text())
    if sha(directory / "manifest.json") != expected["manifest_sha256"]:
        raise ValueError("official build manifest mismatch")
    manifest = json.loads((directory / "manifest.json").read_text())
    for filename, key in (("client.js", "client_js_sha256"), ("dex.json", "data_sha256"),
                          ("provenance.json", "provenance_sha256")):
        if sha(directory / filename) != manifest[key]:
            raise ValueError("official build mismatch: " + filename)
    if revision(CLIENT) != PIN or revision(SERVER) != SERVER_PIN:
        raise ValueError("official client/server revision mismatch")
    provenance = json.loads((directory / "provenance.json").read_text())
    for filename, checksum in provenance["dependencies"].items():
        path = Path(filename) if Path(filename).is_absolute() else CLIENT / filename
        if sha(path) != checksum:
            raise ValueError("official source/lockfile mismatch: " + filename)
    for name, path in (("dependencies", CLIENT / "node_modules"), ("server_dist", SERVER / "dist")):
        if inventory(path) != manifest[name]:
            raise ValueError("official build dependency mismatch: " + name)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("directory", type=Path, nargs="?", default=DEFAULT_BUILD)
    args = parser.parse_args()
    print(json.dumps(create(args.directory) if args.command == "build" else verify(args.directory)))


if __name__ == "__main__":
    main()
