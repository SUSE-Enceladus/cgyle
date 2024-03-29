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
import subprocess
from typing import (
    List, Dict
)

from cgyle.response import Response
from cgyle.exceptions import (
    CgyleCatalogError,
    CgyleCommandError,
    CgylePodmanError
)


class Catalog:
    """
    Read v2 registry catalog
    """
    def __init__(self) -> None:
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
        result: List[str] = []
        server = server.replace('http://', '')
        server = server.replace('https://', '')
        call_args = [
            'podman', 'search',
            f'--tls-verify={format(tls_verify).lower()}',
            '--limit', '2147483647'
        ]
        if creds:
            call_args += [
                '--creds', creds
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
