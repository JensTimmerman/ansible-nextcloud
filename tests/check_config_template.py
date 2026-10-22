#!/usr/bin/env python3
"""Fail if any Jinja template for a PHP file would emit bytes before `<?php`.

Nextcloud's `OC\\Config::readData()` includes `config/config.php` directly, so
any byte before the `<?php` open tag is sent to the web server as page output.
That makes every request emit "headers already sent" warnings and the instance
reports itself as not installed.

The role used to render `config.php.j2` with `{{ ansible_managed }}` on the
first line, i.e. `// Ansible managed` *before* `<?php`, which is exactly the
failure this check catches. The template is fixed, so this is a cheap
regression gate that never needs PHP, Docker or a container.

Usage:
    python3 tests/check_config_template.py [ROOT]

ROOT defaults to the repository root (the parent of this script's directory)
and exists so the check can be pointed at a fixture directory.
"""

import os
import sys

OPEN_TAG = b"<?php"
UTF8_BOM = b"\xef\xbb\xbf"
SNIPPET_BYTES = 40


def find_templates(root):
    """Return every ``*.php.j2`` path under root, sorted, skipping .git."""
    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in (".git", ".tox", "__pycache__"))
        for filename in sorted(filenames):
            if filename.endswith(".php.j2"):
                matches.append(os.path.join(dirpath, filename))
    return sorted(matches)


def describe_first_bytes(data):
    """Render the first bytes of a file as a short, single-line, quoted repr."""
    snippet = data[:SNIPPET_BYTES]
    return repr(snippet.decode("utf-8", "backslashreplace"))


def check_file(path, label):
    """Return a failure message for path, or None when the file starts with `<?php`."""
    with open(path, "rb") as handle:
        data = handle.read()

    if data.startswith(OPEN_TAG):
        return None

    if data.startswith(UTF8_BOM):
        reason = "file starts with a UTF-8 BOM"
    elif data.lstrip()[: len(OPEN_TAG)] == OPEN_TAG:
        reason = "whitespace or a comment precedes the open tag"
    elif not data:
        reason = "file is empty"
    else:
        reason = "file does not start with the open tag"

    return "{0}: {1}; first bytes: {2}".format(label, reason, describe_first_bytes(data))


def main(argv):
    if len(argv) > 2:
        sys.stderr.write("usage: {0} [ROOT]\n".format(os.path.basename(argv[0])))
        return 2

    root = argv[1] if len(argv) == 2 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.abspath(root)

    if not os.path.isdir(root):
        sys.stderr.write("error: {0} is not a directory\n".format(root))
        return 2

    templates = find_templates(root)
    if not templates:
        sys.stderr.write("error: no *.php.j2 templates found under {0}\n".format(root))
        return 1

    failures = []
    for path in templates:
        label = os.path.relpath(path, root).replace(os.sep, "/")
        failure = check_file(path, label)
        if failure:
            failures.append(failure)

    if failures:
        sys.stderr.write("FAIL: PHP templates must start exactly with `<?php`:\n")
        for failure in failures:
            sys.stderr.write("  - {0}\n".format(failure))
        sys.stderr.write(
            "reason: Nextcloud's OC\\Config::readData() includes config.php directly "
            "and rejects any byte before `<?php` (it becomes page output).\n"
        )
        return 1

    print("OK: {0} PHP template(s) start with `<?php`".format(len(templates)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
