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
import json
import requests
import requests.packages.urllib3
from typing import (
    List, Dict
)

from cgyle.exceptions import (
    CgyleJsonError,
    CgyleRequestError,
    CgyleCatalogError
)


class Response:
    """
    Read HTTP response
    """
    def __init__(self) -> None:
        requests.packages.urllib3.disable_warnings()

    def get(self, uri: str) -> dict:
        """
        Send GET request and expect JSON
        """
        try:
            response = requests.request(
                'GET', uri, stream=True, data=None, headers=None
            )
        except Exception as issue:
            raise CgyleRequestError(
                f'Failed to handle request: {issue}'
            )
        try:
            return json.loads(response.content)
        except Exception:
            raise CgyleJsonError(
                'Failed to load response into JSON format: {}'.format(
                    response.content.decode()
                )
            )

    def get_catalog(self, server: str) -> List[str]:
        """
        Read registry catalog from a v2 registry format
        """
        response = Response()
        catalog_dict: Dict[str, List[str]] = response.get(
            f'{server}/v2/_catalog'
        )
        try:
            return catalog_dict['repositories']
        except KeyError:
            raise CgyleCatalogError(
                f'Unexpected catalog response: {catalog_dict}'
            )
