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
import time
from pathlib import Path
from textwrap import dedent
from tempfile import NamedTemporaryFile
import logging
import subprocess
from typing import Optional
from cgyle.catalog import Catalog
from cgyle.exceptions import CgyleCommandError


class DistributionProxy:
    """
    Access methods for the distribution registry
    configured as proxy
    """
    def __init__(self, server: str, container: str = '') -> None:
        self.server = server
        self.container = container
        self.skopeo: Optional[subprocess.Popen[bytes]] = None
        self.registry_name = ''
        self.pid = 0

    def __enter__(self):
        return self

    def update_cache(
        self, tag: str = '', tls_verify: bool = True
    ) -> None:
        """
        Trigger a cache update of the container
        """
        server = self.server
        server = server.replace('http://', '')
        server = server.replace('https://', '')
        tagname = f':{tag}' if tag else ''
        call_args = [
            'skopeo', 'copy',
            f'--src-tls-verify={format(tls_verify).lower()}',
            f'docker://{server}/{self.container}{tagname}',
            f'oci-archive:/dev/null{tagname}'
        ]
        try:
            self.skopeo = subprocess.Popen(
                call_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.pid = self.skopeo.pid
            logging.info(
                '[{}]: Update Container: {}@{}'.format(
                    self.pid, self.container, server
                )
            )
            output, error = self.skopeo.communicate()
            if error:
                logging.error(f'[{self.pid}]: [E] - {error!r}')
            if output:
                logging.info(f'[{self.pid}]: [OK] - {output!r}')
            logging.info(f'[{self.pid}]: [Done]')
        except Exception as issue:
            raise CgyleCommandError(
                'Failed to update cache for: {}: {}'.format(
                    self.container, issue
                )
            )

    def get_pid(self) -> str:
        return format(self.pid)

    def create_local_distribution_instance(
        self, data_dir: str, remote: str, port: int = 5000
    ) -> str:
        self.registry_config = NamedTemporaryFile(prefix='cgyle_local_dist')
        with open(self.registry_config.name, 'w') as config:
            yaml.dump(self._get_distribution_config(remote, port), config)
        logging.info(
            f'Find local registry data at: {os.path.abspath(data_dir)}'
        )
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self.registry_name = f'{os.path.basename(self.registry_config.name)}'
        podman_create_args = [
            'podman', 'run', '--detach', '--name', self.registry_name,
            '-p', f'{port}:{port}',
            '-v', f'{os.path.abspath(data_dir)}/:/var/lib/registry/',
            '-v', f'{self.registry_config.name}:/etc/docker/registry/config.yml',
            'docker.io/library/registry:latest'
        ]
        try:
            podman_create = subprocess.Popen(
                podman_create_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = podman_create.communicate()
            if error:
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
        except Exception as issue:
            raise CgyleCommandError(
                f'Failed to create distribution instance: {issue!r}'
            )

    def _get_distribution_config(self, remote: str, port: int) -> dict:
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
        return config

    def __exit__(self, exc_type, exc_value, traceback):
        if self.registry_name:
            subprocess.Popen(
                ['podman', 'rm', '--force', self.registry_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            ).communicate()
        if exc_type == KeyboardInterrupt:
            if self.pid > 0:
                os.kill(self.pid, 15)
