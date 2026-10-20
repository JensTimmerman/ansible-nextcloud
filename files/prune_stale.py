#!/usr/bin/env python3
"""Delete files present in a live Nextcloud tree but absent from the release.

Why: the role installs by unarchive-merging the release tarball over the
existing tree. Files removed or renamed between majors therefore persist
forever, and a stale controller class can make the router fatal (e.g.
apps/settings/lib/Controller/AppSettingsController.php removed in NC 34).

Safety model:
  * only directories owned by the release are considered:
      - core dirs present in the tarball (lib, core, 3rdparty, dist, ocs,
        ocs-provider, resources), and
      - apps/<id> for ids shipped in the tarball, plus apps/<id> that were
        shipped in the installed tree (core/shipped.json) but are dropped by
        the new release.
  * config/, data/, themes/, third-party apps and top-level loose files are
    never touched;
  * paths containing '..' or starting with '/' are rejected;
  * the run aborts without deleting anything if the stale count exceeds
    --max (default 5000) or the tarball/shipped.json cannot be read.

Prints a JSON summary: {"removed": N, "paths": [...first 20...]}.
"""

import argparse
import json
import os
import subprocess
import sys

CORE_DIRS = {"lib", "core", "3rdparty", "dist", "ocs", "ocs-provider", "resources"}


def tar_files(tarball):
    out = subprocess.run(
        ["tar", "-tf", tarball], check=True, capture_output=True, text=True
    ).stdout
    entries = [line.strip() for line in out.splitlines() if line.strip()]
    tops = {e.split("/", 1)[0] for e in entries if "/" in e}
    top = tops.pop() if len(tops) == 1 else None
    files = set()
    for entry in entries:
        if entry.endswith("/"):
            continue
        path = entry
        if top and path.startswith(top + "/"):
            path = path[len(top) + 1:]
        if path.startswith("./"):
            path = path[2:]
        files.add(path)
    return files


def shipped_apps(root):
    try:
        with open(os.path.join(root, "core", "shipped.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return set(data.get("shippedApps", [])) | set(data.get("alwaysEnabled", []))


def walk_files(root, rel):
    full = os.path.join(root, rel)
    if not os.path.isdir(full):
        return []
    out = []
    for dirpath, _dirnames, filenames in os.walk(full):
        for name in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, name), root))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--tarball", required=True)
    ap.add_argument("--max", type=int, default=5000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    try:
        release = tar_files(args.tarball)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": f"cannot list tarball: {exc}"}))
        return 2

    release_apps = {
        p.split("/")[1] for p in release if p.startswith("apps/") and p.count("/") >= 1
    }
    old_shipped = shipped_apps(root) or set()
    dropped = old_shipped - release_apps

    prefixes = {d for d in CORE_DIRS if any(p == d or p.startswith(d + "/") for p in release)}
    prefixes |= {"apps/" + a for a in release_apps}

    stale = []
    for prefix in prefixes:
        stale.extend(p for p in walk_files(root, prefix) if p not in release)
    for app in dropped:
        stale.extend(walk_files(root, os.path.join("apps", app)))

    bad = [p for p in stale if p.startswith("/") or ".." in p.split("/")]
    if bad:
        print(json.dumps({"error": "unsafe path rejected", "paths": bad[:10]}))
        return 2
    if len(stale) > args.max:
        print(json.dumps({"error": f"refusing to delete {len(stale)} files (max {args.max})"}))
        return 2

    summary = {"removed": len(stale), "dropped_apps": sorted(dropped), "paths": sorted(stale)[:20]}
    if args.dry_run:
        print(json.dumps(summary))
        return 0

    for rel in stale:
        try:
            os.remove(os.path.join(root, rel))
        except FileNotFoundError:
            pass

    # Remove directories left empty inside the release-owned prefixes.
    for prefix in prefixes:
        base = os.path.join(root, prefix)
        for dirpath, _dirnames, _filenames in os.walk(base, topdown=False):
            if os.path.abspath(dirpath) == os.path.abspath(base):
                continue
            try:
                os.rmdir(dirpath)
            except OSError:
                pass

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
