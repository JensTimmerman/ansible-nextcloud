#!/usr/bin/env python3
"""Regression tests for the fail-closed install-mode preflight.

The role must not silently leave an uninstalled host green. These tests run
only `tasks/preflight.yml` against localhost through a temporary wrapper role
whose defaults are a copy of the real `defaults/main.yml`, so no Docker,
packages or root access are needed. They cover:

  * mode=none + installed=false            -> fail before any change
  * mode=web + installed=false             -> skip, no install
  * mode=auto + empty admin password       -> fail
  * mode=auto + peer + empty DB password   -> allowed on a socket
  * mode=auto + password + empty DB pass   -> fail
  * maintenance_install=true (deprecated)  -> resolves to auto

Usage:
    python3 tests/test_install_modes.py

Requires `ansible-playbook` on PATH (the CI lint job installs ansible-core).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFLIGHT = os.path.join(ROOT, "tasks", "preflight.yml")
DEFAULTS = os.path.join(ROOT, "defaults", "main.yml")

BASE_VARS = {
    "nextcloud_db_type": "pgsql",
    "nextcloud_db_host": "localhost",
    "nextcloud_db_name": "nextcloud",
    "nextcloud_db_user": "nextcloud",
    "nextcloud_db_password": "test-db-password",
    "nextcloud_db_auth": "password",
    "nextcloud_admin_user": "admin",
    "nextcloud_admin_password": "test-admin-password",
}


class Case:
    def __init__(self, name, installed=False, fixture=None, mode=None,
                 maintenance_install=None, override=None, expected_mode=None,
                 expected_skipped=False, expect_fail=None, expect_output=None,
                 expect_ok=False):
        self.name = name
        self.fixture = fixture or ("installed" if installed else "missing")
        self.mode = mode
        self.maintenance_install = maintenance_install
        self.override = override or {}
        self.expected_mode = expected_mode or mode or "none"
        self.expected_skipped = expected_skipped
        self.expect_fail = expect_fail
        self.expect_output = expect_output
        self.expect_ok = expect_ok


CASES = [
    Case("none_missing_fails", expect_fail="nextcloud_install_mode=none requires"),
    Case(
        "web_missing_skips",
        mode="web",
        expected_skipped=True,
        expect_output="skipped (mode=web)",
        expect_ok=True,
    ),
    Case(
        "auto_empty_admin_password_fails",
        mode="auto",
        override={"nextcloud_admin_password": ""},
        expect_fail="nextcloud_admin_password",
    ),
    Case(
        "auto_peer_empty_db_password_socket_ok",
        mode="auto",
        override={
            "nextcloud_db_auth": "peer",
            "nextcloud_db_password": "",
            "nextcloud_db_host": "/var/run/postgresql",
        },
        expect_ok=True,
    ),
    Case(
        "auto_password_empty_db_password_fails",
        mode="auto",
        override={"nextcloud_db_password": ""},
        expect_fail="nextcloud_db_password",
    ),
    Case(
        "deprecated_maintenance_install_implies_auto",
        maintenance_install=True,
        expected_mode="auto",
        expect_ok=True,
    ),
    Case("none_installed_ok", installed=True, expect_ok=True),
    Case(
        "web_installed_ok",
        installed=True,
        mode="web",
        expected_skipped=False,
        expect_ok=True,
    ),
    Case(
        "extracted_but_uninstalled_fails_none",
        fixture="extracted",
        expect_fail="nextcloud_install_mode=none requires",
    ),
    Case(
        "invalid_mode_fails",
        installed=True,
        mode="bogus",
        expect_fail="must be one of none, web or auto",
    ),
    Case(
        "peer_requires_pgsql",
        mode="auto",
        override={
            "nextcloud_db_auth": "peer",
            "nextcloud_db_password": "",
            "nextcloud_db_type": "mysql",
            "nextcloud_db_host": "/var/run/postgresql",
        },
        expect_fail="peer is only supported",
    ),
    Case(
        "peer_requires_socket",
        mode="auto",
        override={
            "nextcloud_db_auth": "peer",
            "nextcloud_db_password": "",
            "nextcloud_db_host": "localhost",
        },
        expect_fail="Unix-socket host",
    ),
]


def write_fixture(destination, fixture):
    if fixture == "missing":
        return
    config_dir = os.path.join(destination, "nextcloud", "config")
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(destination, "nextcloud", "version.php"), "w", encoding="utf-8") as handle:
        handle.write('<?php\n$OC_VersionString = "35.0.2";\n')
    if fixture == "installed":
        with open(os.path.join(config_dir, "config.php"), "w", encoding="utf-8") as handle:
            handle.write("<?php\n$CONFIG = array (\n  'installed' => true,\n);\n")


def build_play(case, destination):
    variables = dict(BASE_VARS)
    variables["nextcloud_destination"] = destination
    variables.update(case.override)
    if case.mode is not None:
        variables["nextcloud_install_mode"] = case.mode
    if case.maintenance_install is not None:
        variables["nextcloud_maintenance_install"] = case.maintenance_install

    post_tasks = []
    if case.expect_ok:
        post_tasks = [
            {
                "name": "Assert the resolved install mode",
                "ansible.builtin.assert": {
                    "that": ["nextcloud_install_mode_effective == '{0}'".format(case.expected_mode)],
                    "quiet": True,
                },
            },
            {
                "name": "Assert the skipped flag",
                "ansible.builtin.assert": {
                    "that": [
                        "nextcloud_install_skipped | bool == {0}".format(
                            "true" if case.expected_skipped else "false"
                        )
                    ],
                    "quiet": True,
                },
            },
        ]
    else:
        post_tasks = [
            {
                "name": "Fail because the preflight unexpectedly succeeded",
                "ansible.builtin.fail": {"msg": "expected preflight failure did not happen"},
            }
        ]

    return {
        "name": "Install-mode preflight: {0}".format(case.name),
        "hosts": "localhost",
        "gather_facts": False,
        "vars": variables,
        "roles": [{"role": "nc_preflight"}],
        "post_tasks": post_tasks,
    }


def run_case(workdir, case):
    case_dir = os.path.join(workdir, case.name)
    os.makedirs(case_dir)
    destination = os.path.join(case_dir, "nextcloud-destination")
    write_fixture(destination, case.fixture)

    play_path = os.path.join(case_dir, "play.json")
    with open(play_path, "w", encoding="utf-8") as handle:
        json.dump([build_play(case, destination)], handle, indent=2)

    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = os.path.join(workdir, "ansible.cfg")
    env["ANSIBLE_NOCOLOR"] = "1"
    env["COLUMNS"] = "400"

    completed = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", play_path],
        cwd=workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = completed.stdout

    if case.expect_ok:
        if completed.returncode != 0:
            return "expected success but rc={0}\n{1}".format(completed.returncode, output)
        if case.expect_output and case.expect_output not in output:
            return "expected output {0!r} in\n{1}".format(case.expect_output, output)
        return None

    if completed.returncode == 0:
        return "expected failure but rc=0\n{0}".format(output)
    if case.expect_fail and case.expect_fail not in output:
        return "expected failure message {0!r} in output:\n{1}".format(case.expect_fail, output)
    return None


def main():
    if not os.path.isfile(PREFLIGHT):
        sys.stderr.write("error: {0} not found\n".format(PREFLIGHT))
        return 1
    if shutil.which("ansible-playbook") is None:
        sys.stderr.write("error: ansible-playbook not found on PATH\n")
        return 1

    with tempfile.TemporaryDirectory(prefix="nc-install-modes-") as workdir:
        role_dir = os.path.join(workdir, "roles", "nc_preflight")
        os.makedirs(os.path.join(role_dir, "tasks"))
        os.makedirs(os.path.join(role_dir, "defaults"))
        shutil.copy2(DEFAULTS, os.path.join(role_dir, "defaults", "main.yml"))
        with open(os.path.join(role_dir, "tasks", "main.yml"), "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                "- name: \"Include the role preflight\"\n"
                "  ansible.builtin.include_tasks: \"{0}\"\n".format(PREFLIGHT)
            )
        with open(os.path.join(workdir, "ansible.cfg"), "w", encoding="utf-8") as handle:
            handle.write(
                "[defaults]\n"
                "roles_path = ./roles\n"
                "interpreter_python = auto_silent\n"
                "retry_files_enabled = False\n"
            )

        failures = []
        for case in CASES:
            failure = run_case(workdir, case)
            if failure:
                failures.append("{0}: {1}".format(case.name, failure))
                print("FAIL: {0}".format(case.name))
            else:
                print("PASS: {0}".format(case.name))

    if failures:
        sys.stderr.write("\n{0} install-mode preflight test(s) failed:\n".format(len(failures)))
        for failure in failures:
            sys.stderr.write("  - {0}\n".format(failure))
        return 1

    print("\nOK: {0} install-mode preflight cases passed".format(len(CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
