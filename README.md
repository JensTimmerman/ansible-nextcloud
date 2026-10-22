> **Maintained fork.** This is the maintained fork of
> [swcc/ansible-nextcloud](https://github.com/swcc/ansible-nextcloud), which is
> unmaintained (last commit 2020). This fork adds Remi modular PHP support,
> fresh-install support, release-manifest pruning and CI (Molecule on Rocky 9
> and Ubuntu 24.04).


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

Makefile for easier Ansible usage
------------------

I have written a small Makefile to make your future ansible runs easier. Don't hesitate to [check it out](https://github.com/paulRbr/ansible-makefile/).

Download the `*.deb` package from the github releases, install it and start using it with `ansible-make help`.

License
-------

GPLv3
