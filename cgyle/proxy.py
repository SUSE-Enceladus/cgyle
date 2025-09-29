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
from cgyle.credentials import Credentials
from cgyle.catalog import Catalog
from cgyle.exceptions import CgyleCommandError
from json import JSONDecodeError
from subprocess import SubprocessError
from typing import List


class DistributionProxy:
    """
    Access methods for the distribution registry
    configured as proxy
    """
    def __init__(self, server: str, container: str = '') -> None:
        self.log_path = DistributionProxy.get_log_path()
        self.server = server.replace('http://', '')
        self.server = self.server.replace('https://', '')
        self.container = container
        self.registry_name = ''
        self.shutdown = False
        self.pid = 0

    def __enter__(self):
        return self

    @staticmethod
    def get_log_path():
        return '/var/log/cgyle'

    def get_tags(
        self, tls_verify: bool = True, proxy_creds: str = '',
        arch: str = '', tag_log_name: str = '',
        with_signatures: bool = False,
        with_attributes: bool = False
    ) -> List[str]:
        username, password = Credentials.read(proxy_creds)
        call_args = [
            'skopeo'
        ]
        arch = '' if arch == 'all' else arch
        if arch:
            call_args += [
                '--override-arch', arch
            ]
        call_args.append('inspect')
        if username and password:
            call_args += ['--creds', f'{username}:{password}']
        call_args += [
            f'--tls-verify={format(tls_verify).lower()}',
            f'docker://{self.server}/{self.container}'
        ]
        tag_list: List[str] = []
        try:
            output, error, returncode = self._call_skopeo(
                call_args
            )
            if returncode != 0:
                # If skopeo could not read the manifest, try a podman search
                call_args = [
                    'podman', 'search', '--list-tags',
                    '--no-trunc', '--format', '{{.Tag}}',
                    f'{self.server}/{self.container}'
                ]
                if username and password:
                    call_args += ['--creds', f'{username}:{password}']
                output, error, returncode = self._call_skopeo(
                    call_args
                )
                if returncode != 0:
                    raise SubprocessError(error)
                else:
                    if arch and arch not in Catalog.get_container_arch_list():
                        return []
                    tag_list = output.strip().decode().split(
                        os.linesep
                    ) if output else []
            else:
                config = json.loads(output)
                if arch and config.get('Architecture') != arch:
                    return []
                tag_list = config.get('RepoTags') or []
        except (SubprocessError, JSONDecodeError) as issue:
            raise CgyleCommandError(
                'Failed to get tag list for: {}: {}'.format(
                    self.container, issue
                )
            )
        result_tag_list = []
        for tag in tag_list:
            if tag.endswith('.sig') and with_signatures:
                # Add signature tag for signature verification. Only
                # makes sense if signed containers are allowed on
                # the target registry
                result_tag_list.append(tag)
            elif tag.endswith('.att') and with_attributes:
                # Add attribute tag for custom attributes, e.g sboms
                result_tag_list.append(tag)
            else:
                result_tag_list.append(tag)
        if tag_log_name:
            with open(tag_log_name, 'w') as taglog:
                for tag in result_tag_list:
                    if tag != 'latest':
                        taglog.write(f'{tag}{os.linesep}')
        return result_tag_list

    def update_cache(
        self, from_registry: str, tls_verify: bool = True,
        store_oci: str = '', push_oci: str = '', push_oci_creds: str = '',
        proxy_creds: str = '', use_archs: List[str] = [],
        remove_signatures: bool = False,
        with_signing_tags: bool = False,
        with_attribute_tags: bool = False
    ) -> None:
        """
        Trigger a cache update of the container
        """
        username, password = Credentials.read(proxy_creds)
        push_username, push_password = Credentials.read(push_oci_creds)
        server = self.server
        Path(self.log_path).mkdir(parents=True, exist_ok=True)
        if store_oci:
            Path(store_oci).mkdir(parents=True, exist_ok=True)

        if not use_archs:
            use_archs.append('all')

        try:
            for arch in use_archs:
                count = 0
                if self.shutdown:
                    break
                if store_oci:
                    tag_log_name = '{}/{}-{}.tags'.format(
                        store_oci, self.container, arch
                    )
                else:
                    tag_log_name = '{}/{}-{}.tags'.format(
                        self.log_path, self.container, arch
                    )
                Path(os.path.dirname(tag_log_name)).mkdir(
                    parents=True, exist_ok=True
                )
                prior_tag_list = []
                if os.path.exists(tag_log_name):
                    with open(tag_log_name) as taglog:
                        prior_tag_list = [tag.rstrip() for tag in taglog]
                tag_list = DistributionProxy(
                    from_registry, self.container
                ).get_tags(
                    tls_verify, proxy_creds, arch, tag_log_name,
                    with_signing_tags, with_attribute_tags
                )
                tag_list = \
                    [tag for tag in tag_list if tag not in prior_tag_list]
                for tagname in tag_list:
                    count += 1
                    if store_oci:
                        archive_name = '{}/{}-{}-{}.oci.tar'.format(
                            store_oci, self.container, tagname, arch
                        )
                        log_name = '{}/{}-{}-{}.log'.format(
                            store_oci, self.container, tagname, arch
                        )
                    elif push_oci:
                        archive_name = '{}/{}'.format(
                            push_oci, self.container
                        )
                        log_name = '{}/{}-{}-{}.log'.format(
                            self.log_path, self.container, tagname, arch
                        )
                    else:
                        archive_name = '/dev/null'
                        log_name = '{}/{}-{}-{}.log'.format(
                            self.log_path, self.container, tagname, arch
                        )
                    Path(os.path.dirname(log_name)).mkdir(
                        parents=True, exist_ok=True
                    )
                    if arch == 'all':
                        call_args = [
                            'skopeo', 'copy', '--all'
                        ]
                    else:
                        call_args = [
                            'skopeo', '--override-arch', arch, 'copy'
                        ]
                    call_args += [
                        '--dest-oci-accept-uncompressed-layers',
                        '--retry-times', '5',
                        '--image-parallel-copies', '5',
                        f'--src-tls-verify={format(tls_verify).lower()}'
                    ]
                    if remove_signatures:
                        call_args += [
                            '--remove-signatures'
                        ]
                    if username and password:
                        call_args += [
                            '--src-creds', f'{username}:{password}'
                        ]
                    if push_username and push_password:
                        call_args += [
                            '--dest-creds', f'{push_username}:{push_password}'
                        ]
                    call_args += [
                        f'docker://{server}/{self.container}:{tagname}'
                    ]
                    if push_oci:
                        call_args += [
                            f'docker://{archive_name}:{tagname}'
                        ]
                    else:
                        call_args += [
                            f'oci-archive:{archive_name}:{tagname}'
                        ]
                    with open(log_name, 'a') as clog:
                        skopeo = subprocess.Popen(
                            call_args, stdout=clog, stderr=clog
                        )
                        self.pid = skopeo.pid
                        logging.info(
                            '[{}]: Fetching ({}/{} tags, arch:{}): {}:{}@{}'.format(
                                self.pid, count, len(tag_list), arch,
                                self.container, tagname, server
                            )
                        )
                        skopeo.communicate()
                        if skopeo.returncode != 0:
                            logging.error(
                                '[{}]: [E] - for details see: {}'.format(
                                    self.pid, log_name
                                )
                            )
                            # something went wrong with this container tag.
                            # Rewrite the tag list and drop this tag from the list
                            # such that it gets taken into account for the next
                            # run of cgyle
                            current_tag_list = []
                            if os.path.exists(tag_log_name):
                                with open(tag_log_name) as taglog:
                                    current_tag_list = [tag.rstrip() for tag in taglog]
                                with open(tag_log_name, 'w') as taglog:
                                    for tag in current_tag_list:
                                        if tag != tagname:
                                            taglog.write(f'{tag}{os.linesep}')
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
        username, password = Credentials.read(proxy_creds)
        status = ''
        try:
            scheduler_state_file = f'{os.path.abspath(data_dir)}/scheduler-state.json'
            if not self._scheduler_state_ok(scheduler_state_file):
                status = f'Deleting invalid state file {scheduler_state_file}'
                os.unlink(scheduler_state_file)
            status = f'Creating {self.registry_config.name}'
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
            cgyle_oci_distribution_check = subprocess.Popen(
                ['podman', 'image', 'exists', 'registry'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            cgyle_oci_distribution_check.communicate()
            if cgyle_oci_distribution_check.returncode != 0:
                podman_load_args = [
                    'podman', 'load', '-i',
                    '/usr/share/cgyle-oci-distribution/cgyle-oci-distribution.tar'
                ]
                podman_load = subprocess.Popen(
                    podman_load_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                output, error = podman_load.communicate()
                if podman_load.returncode != 0:
                    raise CgyleCommandError(
                        f'Failed to load cgyle distribution container: {error!r}'
                    )
            proxy_log = f'{self.log_path}_proxy.log'
            status = f'Create/Append {proxy_log}'
            with open(proxy_log, 'a'):
                # Create or append to proxy log
                pass
            podman_create_args = [
                'podman', 'run', '--detach', '--name', self.registry_name,
                '--rm',
                '--net', 'host',
                '-v',
                f'{os.path.abspath(data_dir)}/:/var/lib/registry/',
                '-v',
                f'{self.registry_config.name}:/etc/docker/registry/config.yml',
                '-v', f'{proxy_log}:{proxy_log}',
                '-v', '/etc/pki/:/etc/pki/',
                '-v', '/etc/hosts:/etc/hosts',
                '-v', '/etc/ssl/:/etc/ssl/',
                '-v', '/var/lib/ca-certificates/:/var/lib/ca-certificates/',
                'registry:latest',
                'sh', '-c', f'registry serve /etc/docker/registry/config.yml &>{proxy_log}'
            ]
            status = f'Run podman process {podman_create_args}'
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
                f'Failed to create distribution instance: {status} {issue!r}'
            )

    def _scheduler_state_ok(self, state_file: str) -> bool:
        """
        Check if current scheduler state file of the distribution
        registry is valid.
        """
        if os.path.exists(state_file):
            try:
                with open(state_file) as json_file:
                    json.load(json_file)
            except JSONDecodeError:
                return False
        return True

    def _call_skopeo(self, call_args: List[str]) -> list:
        skopeo = subprocess.Popen(
            call_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output, error = skopeo.communicate()
        return [output, error, skopeo.returncode]

    def _get_distribution_config(
        self, remote: str, port: int, username: str, password: str
    ) -> dict:
        config_string = dedent('''
            version: 0.1
            log:
              accesslog:
                disabled: false
              level: debug
              formatter: json
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
