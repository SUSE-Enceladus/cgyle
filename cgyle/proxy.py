# Copyright (c) 2024 SUSE Software Solutions Germany GmbH.  All rights reserved.
#
# This file is part of cgyle.
#
# cgyle is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# cgyle is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with cgyle.  If not, see <http://www.gnu.org/licenses/>
#
import os
import yaml
import json
import time
import psutil
from pathlib import Path
from textwrap import dedent
from tempfile import NamedTemporaryFile
import logging
import subprocess
from typing import Optional
from cgyle.catalog import Catalog
from cgyle.exceptions import (
    CgyleCommandError, CgyleCredentialsError
)
from json import JSONDecodeError
from subprocess import SubprocessError
from typing import List


class DistributionProxy:
    """
    Access methods for the distribution registry
    configured as proxy
    """
    def __init__(self, server: str, container: str = '') -> None:
        self.log_path = '/var/log/cgyle'
        self.server = server.replace('http://', '')
        self.server = self.server.replace('https://', '')
        self.container = container
        self.skopeo: Optional[subprocess.Popen[bytes]] = None
        self.registry_name = ''
        self.shutdown = False
        self.pid = 0

    def __enter__(self):
        return self

    def get_tags(
        self, tls_verify: bool = True, proxy_creds: str = ''
    ) -> List[str]:
        username, password = self._get_credentials(proxy_creds)
        call_args = [
            'skopeo', 'inspect'
        ]
        if username and password:
            call_args += ['--creds', f'{username}:{password}']
        call_args += [
            f'--tls-verify={format(tls_verify).lower()}',
            f'docker://{self.server}/{self.container}'
        ]
        try:
            self.skopeo = subprocess.Popen(
                call_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = self.skopeo.communicate()
            if self.skopeo.returncode != 0:
                raise SubprocessError(error)
            config = json.loads(output)
            return config.get('RepoTags') or []
        except (SubprocessError, JSONDecodeError) as issue:
            raise CgyleCommandError(
                'Failed to get tag list for: {}: {}'.format(
                    self.container, issue
                )
            )

    def update_cache(
        self, tags: List[str], tls_verify: bool = True,
        store_oci: str = '', proxy_creds: str = ''
    ) -> None:
        """
        Trigger a cache update of the container
        """
        username, password = self._get_credentials(proxy_creds)
        server = self.server
        Path(self.log_path).mkdir(parents=True, exist_ok=True)
        if store_oci:
            Path(store_oci).mkdir(parents=True, exist_ok=True)
        count = 0
        for tagname in tags:
            count += 1
            if self.shutdown:
                break
            if store_oci:
                archive_name = '{}/{}-{}.oci.tar'.format(
                    store_oci, self.container, tagname
                )
                log_name = '{}/{}-{}.log'.format(
                    store_oci, self.container, tagname
                )
            else:
                archive_name = '/dev/null'
                log_name = '{}/{}-{}.log'.format(
                    self.log_path, self.container, tagname
                )
            Path(os.path.dirname(log_name)).mkdir(
                parents=True, exist_ok=True
            )
            call_args = [
                'skopeo', 'copy', '--all',
                f'--src-tls-verify={format(tls_verify).lower()}'
            ]
            if username and password:
                call_args += [
                    '--src-creds', f'{username}:{password}'
                ]
            call_args += [
                f'docker://{server}/{self.container}:{tagname}',
                f'oci-archive:{archive_name}:{tagname}'
            ]
            try:
                with open(log_name, 'a') as clog:
                    self.skopeo = subprocess.Popen(
                        call_args, stdout=clog, stderr=clog
                    )
                    self.pid = self.skopeo.pid
                    logging.info(
                        '[{}]: Fetch Container ({}/{} tags): {}:{}@{}'.format(
                            self.pid, count, len(tags),
                            self.container, tagname, server
                        )
                    )
                    self.skopeo.communicate()
                    if self.skopeo.returncode != 0:
                        logging.error(
                            '[{}]: [E] - for details see: {}'.format(
                                self.pid, log_name
                            )
                        )
                    else:
                        os.unlink(log_name)
                    logging.info(f'[{self.pid}]: [Done]')
            except (SubprocessError, IOError) as issue:
                raise CgyleCommandError(
                    'Failed to update cache for: {}: {}'.format(
                        self.container, issue
                    )
                )

    def get_pid(self) -> str:
        return format(self.pid)

    def create_local_distribution_instance(
        self, data_dir: str, remote: str, port: int = 7000,
        proxy_creds: str = ''
    ) -> str:
        self.registry_config = NamedTemporaryFile(prefix='cgyle_local_dist')
        username, password = self._get_credentials(proxy_creds)
        try:
            with open(self.registry_config.name, 'w') as config:
                yaml.dump(
                    self._get_distribution_config(
                        remote, port, username, password
                    ),
                    config
                )
            logging.info(
                f'Find local registry data at: {os.path.abspath(data_dir)}'
            )
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            self.registry_name = \
                f'{os.path.basename(self.registry_config.name)}'
            podman_create_args = [
                'podman', 'run', '--detach', '--name', self.registry_name,
                '--net', 'host',
                '-v',
                f'{os.path.abspath(data_dir)}/:/var/lib/registry/',
                '-v',
                f'{self.registry_config.name}:/etc/docker/registry/config.yml',
                '-v', '/etc/pki/:/etc/pki/',
                '-v', '/etc/hosts:/etc/hosts',
                '-v', '/etc/ssl/:/etc/ssl/',
                '-v', '/var/lib/ca-certificates/:/var/lib/ca-certificates/',
                'docker.io/library/registry:latest'
            ]
            podman_create = subprocess.Popen(
                podman_create_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = podman_create.communicate()
            if error and podman_create.returncode != 0:
                raise CgyleCommandError(
                    f'Failed to create distribution instance: {error!r}'
                )

            registry_url = f'http://localhost:{port}'
            retry = 0
            max_retry = 10
            catalog_issue = ''
            catalog = Catalog()
            while retry < max_retry:
                try:
                    catalog.get_catalog(registry_url)
                    break
                except Exception as issue:
                    catalog_issue = format(issue)
                    time.sleep(1)
                    retry += 1
            if retry >= max_retry:
                raise CgyleCommandError(
                    f'Distribution instance not reachable: {catalog_issue}'
                )
            return registry_url
        except (SubprocessError, IOError) as issue:
            raise CgyleCommandError(
                f'Failed to create distribution instance: {issue!r}'
            )

    def _get_distribution_config(
        self, remote: str, port: int, username: str, password: str
    ) -> dict:
        config_string = dedent('''
            version: 0.1
            log:
              fields:
                service: registry
            storage:
              cache:
                blobdescriptor: inmemory
              filesystem:
                rootdirectory: /var/lib/registry
              delete:
                enabled: true
            http:
              addr: :SOME
              headers:
                X-Content-Type-Options: [nosniff]
            health:
              storagedriver:
                enabled: true
                interval: 10s
                threshold: 3
            proxy:
              remoteurl: SOME
              ttl: 168h
        ''').strip()
        config = yaml.safe_load(config_string)
        config['http']['addr'] = f':{port}'
        config['proxy']['remoteurl'] = remote
        if username and password:
            config['proxy']['username'] = username
            config['proxy']['password'] = password
        return config

    def _get_credentials(self, proxy_creds: str) -> List[str]:
        username = ''
        password = ''
        if proxy_creds:
            try:
                username, password = proxy_creds.split(':')
            except ValueError:
                raise CgyleCredentialsError(
                    f'Invalid credentials, expected user:pass, got {proxy_creds}'
                )
        return [username, password]

    def __exit__(self, exc_type, exc_value, traceback):
        if self.registry_name:
            subprocess.Popen(
                ['podman', 'rm', '--force', self.registry_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            ).communicate()
        if exc_type == KeyboardInterrupt:
            # kill current skopeo call if present
            if self.pid > 0 and psutil.pid_exists(self.pid):
                os.kill(self.pid, 15)
            # set flag to close thread
            self.shutdown = True
