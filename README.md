> **Maintained fork.** This is the maintained fork of
> [swcc/ansible-nextcloud](https://github.com/swcc/ansible-nextcloud), which is
> unmaintained (last commit 2020). This fork adds Remi modular PHP support,
> fresh-install support with fail-closed install modes, release-manifest
> pruning and CI (Molecule on Rocky 9 and Ubuntu 24.04).


## php-fpm dependency

This role installs the PHP packages it needs, including `php-fpm` (the
`phpX.Y-fpm` package on Debian/Ubuntu and `php-fpm` on the Remi modular
stream). It does **not** configure php-fpm pools.

The previous hard dependency on `NBZ4live/ansible-php-fpm` was removed: that
role is unmaintained (last commit 2020) and its `include:` tasks with extra
params are rejected by ansible-core >= 2.14. If you want the pool/config
handling, add that role to your play explicitly (or use your own php-fpm
configuration).

Nextcloud Ansible role
=========

[![Build Status](https://travis-ci.org/swcc/ansible-nextcloud.svg?branch=master)](https://travis-ci.org/swcc/ansible-nextcloud) [![Ansible Galaxy](https://img.shields.io/badge/role-swcc.ansible__nextcloud-blue.svg)](https://galaxy.ansible.com/swcc/ansible-nextcloud)

Installs nextcloud from [nextcloud.com servers](https://download.nextcloud.com/) sources. This role assumes you will run nextcloud with `PHP-FPM` and thus installs it for you as an ansible role dependency (with the [`NBZ4live.php-fpm`](https://github.com/NBZ4live/ansible-php-fpm) role.

Example Playbook
----------------

Basic example playbook:

```yaml
- hosts: webservers
  roles:
    - role: swcc.nextcloud
      nextcloud_destination: /home/nextcloud
      nextcloud_version: 19.0.3
```

Role parameters
----------------

| Variable                                  | Default    | Type            | Description                                                                                                                                                                                                                                                                                     |
| -----------------------                   | :------:   | :-------------: | ------------                                                                                                                                                                                                                                                                                    |
| `nextcloud_version`                       | `20.0.2`   | `string`        | Which nextcloud version to install                                                                                                                                                                                                                                                              |
| `nextcloud_destination`                   | `/var/www` | `string`        | Where to install Nextcloud (will be installed in "{{ nextcloud_destination}}/nextcloud/" directory on your filesystem)                                                                                                                                                                          |
| `nextcloud_dir_user`                      | `www-data` | `string`        | Which unix user should own the installed directory                                                                                                                                                                                                                                              |
| `nextcloud_dir_group`                     | `www-data` | `string`        | Which unix group should own the installed directory                                                                                                                                                                                                                                             |
| `nextcloud_php_memory_limit`              | `512M`     | `string`        | Php memory_limit setting. Default recommanded by Nextcloud is 512M.                                                                                                                                                                                                                             |
| `nextcloud_install_mode`                  | `none`     | `string`        | Fail-closed install behaviour when Nextcloud is not installed: `none` fails before any change, `web` deploys only and skips install/config, `auto` runs `occ maintenance:install`. See [Install modes](#install-modes-fail-closed).                                                              |
| `nextcloud_db_auth`                       | `password` | `string`        | Database authentication for the fresh-install preflight: `password` (non-empty `nextcloud_db_password`) or `peer` (PostgreSQL over a Unix socket only, empty password allowed).                                                                                                                    |
| `nextcloud_maintenance_install`           | `false`    | `bool`          | **Deprecated.** `true` implies `nextcloud_install_mode: auto` when `nextcloud_install_mode` is not set. Use `nextcloud_install_mode` instead.                                                                                                                                                    |
| `nextcloud_config`                        | `{}`       | `dict`          | a dict object of key values to set in the `config/config.php` file of Nextcloud. Beware of the content as they need to be valid PHP values. E.g. a string should be defined in your ansible dictionnary as `"'mystring'"` for the value to be the litteral `'mystring'` in the config.php file. |
| `nextcloud_trusted_domains`               | `[]`       | `list`          | List of trusted domains applied idempotently via `occ config:system:set trusted_domains <i> --value=<item>` as the Nextcloud owner. Empty list = no-op. Applied **after** `nextcloud_config`, so when both set `trusted_domains` the values here win. Surplus indices are deleted (`occ config:system:delete`) when the list shrinks.                                                                                              |
| `nextcloud_trusted_proxies`               | `[]`       | `list`          | List of trusted reverse proxies, applied via `occ` exactly like `nextcloud_trusted_domains` (key `trusted_proxies`). Empty list = no-op.                                                                                                                                                                                                                          |
| `nextcloud_forwarded_for_headers`         | `[]`       | `list`          | List of forwarded-for headers, applied via `occ` exactly like `nextcloud_trusted_domains` (key `forwarded_for_headers`). Empty list = no-op.                                                                                                                                                                                                                     |
| `nextcloud_onlyoffice_force_flush_period` | undefined  | `string`        | Hack taken from https://help.nextcloud.com/t/onlyoffice-data-loss/20586/5 to flush onlyoffice changes to disk at regular intervals. E.g. value can be `300s` to flush data every 5 minutes.                                                                                                     |

_Optional_, backup related variables:

| Variable                              | Default                                     | Type            | Description                                                                                             |
| -----------------------               | :------:                                    | :-------------: | ------------                                                                                            |
| `nextcloud_backup`                    | -                                           | `object`        | Define this object if you want to backup both the database and the data dir of your Nextcloud instance. |
| `nextcloud_backup.destination_server` | -                                           | `string`        | Destination backup server which will receive all files (via `rsync`)                                    |
| `nextcloud_backup.retention`          | `7`                                         | `number`        | Number of days of database backups to keep on the instance                                              |
| `nextcloud_backup.directory`          | `nextcloud_destination + '/nextcloud/data'` | `string`        | Path of the Nextcloud data directory to backup                                                          |
| `nextcloud_backup.pg`                 | -                                           | `object`        | Connection details to the database. See below for details of the object keys.                           |
| `nextcloud_backup.pg.pg_dump_binary`  | -                                           | `string`        | Path of the `pg_dump` binary on the server                                                              |
| `nextcloud_backup.pg.host`            | `localhost`                                 | `string`        | Host of the postgresql database                                                                         |
| `nextcloud_backup.pg.port`            | `5432`                                      | `string`        | Port of the postgresql database                                                                         |
| `nextcloud_backup.pg.dbname`          | `nextcloud`                                 | `string`        | Name of the postgresql database                                                                         |
| `nextcloud_backup.pg.username`        | `nextcloud`                                 | `string`        | User of the postgresql database                                                                         |
| `nextcloud_backup.pg.password`        | -                                           | `string`        | Password of the postgresql database                                                                     |

_⚠️ Please also check the php-fpm variables of the dependent [php-fpm ansible role](https://github.com/NBZ4live/ansible-php-fpm#role-variables) before running this current role. ⚠️_

Most importantly check the php version you want to run by setting the `php_fpm_version` variable. Here is an example configuration of the `php-fpm` dependent role which should suit most needs:

```yaml
php_fpm_version: 7.4

php_fpm_pool_defaults:
  pm: dynamic
  pm.max_children: 10
  pm.start_servers: 2
  pm.min_spare_servers: 1
  pm.max_spare_servers: 4
php_fpm_pools:
  - name: www
    user: www-data
    group: www-data
    listen: "/run/php/php{{ php_fpm_version }}-fpm.sock"
    listen.owner: www-data
    listen.group: www-data
    chdir: /var/www
    env:
      PATH: "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
      TMPDIR: "/tmp"
      TMP: "/tmp"
      HOSTNAME: "$HOSTNAME"
```

Install modes (fail-closed)
---------------------------

`nextcloud_install_mode` controls what happens when Nextcloud is not
installed (`version.php`/`config.php` report `installed=false`). The
preflight runs before any package, directory, download or configuration task,
so a missing instance can no longer leave the play green with `changed=0`.

| Mode   | Behaviour when Nextcloud is not installed |
| ------ | ----------------------------------------- |
| `none` (default) | The role **fails before any change** with remediation instructions: complete the web installer, use `web`, or use `auto` with credentials. |
| `web`  | The role deploys the release, prints `skipped (mode=web)`, and skips `occ maintenance:install` plus post-install configuration (cron, config.php edits, trusted domains, maintenance). Finish the setup in the browser at `https://<host>/index.php`, then rerun the role. |
| `auto` | The role runs `occ maintenance:install` when the instance is missing, then applies the normal configuration. Requires `nextcloud_admin_password` and database credentials. |

When the instance is already installed, every mode manages it normally: the
preflight only decides what to do for a missing instance. Upgrades and release
deployment are not affected.

`nextcloud_maintenance_install: true` is deprecated. When
`nextcloud_install_mode` is not set explicitly, it still resolves to `auto`,
so existing playbooks keep working; setting `nextcloud_install_mode`
explicitly wins. The role logs a deprecation warning whenever the old flag is
used.

This is deliberately a behaviour change: an uninstalled host with
`nextcloud_maintenance_install: false` used to produce only a warning while
the play stayed green. It now fails in the default `none` mode. Playbooks that
deploy the release and use the browser installer should set
`nextcloud_install_mode: web`.

Database authentication
-----------------------

`nextcloud_db_auth` selects how the fresh-install path connects to the
database:

- `password` (default): `nextcloud_db_password` must be non-empty. An empty
  password remains allowed for `sqlite`.
- `peer`: only supported with `nextcloud_db_type: pgsql` and a Unix-socket
  host (`/var/run/postgresql` or `localhost:/var/run/postgresql`). An empty
  `nextcloud_db_password` is allowed; PostgreSQL authenticates the OS user
  running `occ` (`nextcloud_dir_user`).

Before `occ maintenance:install`, the role probes the PostgreSQL connection
as `nextcloud_dir_user` with `pg_connect` (mode `auto` and PostgreSQL only).
The probe is read-only and fails with an actionable message when the socket,
database role or password is wrong. For `peer`, ensure the socket directory is
reachable by `nextcloud_dir_user` and that its OS user matches the database
role.

config.php repair
-----------------

Nextcloud refuses a config file that has any bytes before the `<?php` open
tag; every `occ` call then fails with:

```
Exception: Config file has leading content, please remove everything before "<?php" in config.php
```

On every run, **before the first `occ` call**, the role checks
`{{ nextcloud_destination }}/nextcloud/config/config.php`. When the `<?php`
tag is not at offset 0, it rewrites the file from that tag onwards, so the
stray leading bytes (for example legacy `nextcloud_config` values inserted
above `<?php`) are dropped. The rewrite:

- keeps ownership and permissions (`{{ nextcloud_dir_user }}:{{ nextcloud_dir_group }}`, mode `0640`),
- leaves a timestamped `config.php.*~` backup next to the file (Nextcloud ignores it),
- is idempotent (a valid file has offset 0 and is never rewritten),
- never executes the leading bytes: they are discarded, not interpreted,
- is fully `no_log` (config.php contains the database password and instance secret).

A non-empty file with no `<?php` tag at all cannot be repaired safely and
makes the role fail with an explicit message; restore it from a backup. A
zero-byte `config.php` is left untouched, since that is the normal "not
installed yet" state detected via `occ status`.

`templates/config.php.j2` now starts with `<?php` too (the `ansible_managed`
comment moved inside the PHP document), so a config file created by this role
is valid for Nextcloud.

Makefile for easier Ansible usage
------------------

I have written a small Makefile to make your future ansible runs easier. Don't hesitate to [check it out](https://github.com/paulRbr/ansible-makefile/).

Download the `*.deb` package from the github releases, install it and start using it with `ansible-make help`.

License
-------

GPLv3
