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
import re
import yaml
import subprocess
from typing import (
    List, Dict
)

from cgyle.credentials import Credentials
from cgyle.response import Response
from cgyle.exceptions import (
    CgyleCatalogError,
    CgyleCommandError,
    CgylePodmanError,
    CgyleFilterExpressionError
)


class Catalog:
    """
    Read v2 registry catalog
    """
    def __init__(self) -> None:
        self.archs = Catalog.get_arch_list()
        self.response = Response()

    def get_catalog(self, server: str) -> List[str]:
        """
        Read registry catalog from a v2 registry format
        """
        catalog_dict: Dict[str, List[str]] = self.response.get(
            f'{server}/v2/_catalog'
        )
        try:
            return catalog_dict['repositories']
        except KeyError:
            raise CgyleCatalogError(
                f'Unexpected catalog response: {catalog_dict}'
            )

    def get_catalog_podman_search(
        self, server: str, tls_verify: bool = True, creds: str = ''
    ) -> List[str]:
        """
        Read registry catalog using podman search
        """
        username, password = Credentials.read(creds)
        result: List[str] = []
        server = server.replace('http://', '')
        server = server.replace('https://', '')
        call_args = [
            'podman', 'search',
            f'--tls-verify={format(tls_verify).lower()}',
            '--limit', '2147483647'
        ]
        if username and password:
            call_args += [
                '--creds', f'{username}:{password}'
            ]
        call_args.append(
            f'{server}:/'
        )
        try:
            self.podman = subprocess.Popen(
                call_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = self.podman.communicate()
            if error and self.podman.returncode != 0:
                raise CgylePodmanError(
                    f'podman search failed with: {error.decode()}'
                )
            if output:
                result = []
                for line in output.decode().split(os.linesep):
                    server, slash, container = line.partition(os.sep)
                    container = container.strip()
                    if container:
                        result.append(container)
        except CgylePodmanError:
            raise
        except Exception as issue:
            raise CgyleCommandError(
                f'Failed to call podman search: {issue}'
            )
        return result

    def apply_filter(
        self, catalog: List[str], rules: List[str]
    ) -> List[str]:
        result: List[str] = []
        for entry in catalog:
            for pattern in rules:
                try:
                    if re.match(pattern, entry):
                        result.append(entry)
                        break
                except Exception as issue:
                    raise CgyleFilterExpressionError(
                        f'Invalid expression [{pattern}]: {issue}'
                    )
        return sorted(result)

    def translate_policy(
        self, policy_file: str,
        skip_sections: List[str] = [], use_archs: List[str] = []
    ) -> List[str]:
        result: List[str] = []
        skip_archs = []
        if use_archs:
            skip_archs = self.archs
            skip_archs = list(filter(lambda i: i not in use_archs, skip_archs))
        with open(policy_file) as policy:
            policy_dict = yaml.safe_load(policy)
            for category in policy_dict:
                if category not in skip_sections:
                    for pattern in policy_dict.get(category):
                        if not next(
                            (arch for arch in skip_archs if arch in pattern), None
                        ):
                            pattern = re.sub('(?<!\*)\*(?!\*)', '[^/]*', pattern)
                            pattern = re.sub('\*\*', '.*', pattern)
                            result.append(f'^{pattern}$')
        return result

    @staticmethod
    def get_arch_list() -> List[str]:
        return [
            'amd64', 'x86_64', 'arm64', 'aarch64', 's390x', 'ppc64el', 'ppc64le'
        ]
