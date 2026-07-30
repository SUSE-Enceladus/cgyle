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
import re
import json
import requests
import requests.packages.urllib3
from urllib.parse import urlencode
from typing import (
    Optional, Any
)

from cgyle.exceptions import CgyleRequestError


class Response:
    """
    Read HTTP response
    """
    def __init__(self) -> None:
        requests.packages.urllib3.disable_warnings()

    def get_auth_challenge(self, target: str) -> Optional[str]:
        """
        Retrieve Www-Authenticate information from
        request target header
        """
        return self.fetch(target).get('www-authenticate')

    def extract_bearer_parameters(
        self, challenge: str
    ) -> tuple[Optional[str], Optional[str]]:
        realm = re.search(r'realm="([^"]+)"', challenge, re.IGNORECASE)
        service = re.search(r'service="([^"]+)"', challenge, re.IGNORECASE)
        return (
            realm.group(1) if realm else None,
            service.group(1) if service else None,
        )

    def fetch(
        self,
        target: str,
        parameters: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        user: str = '',
        password: str = '',
        timeout: int = 300
    ) -> dict[str, Any]:
        """
        Fetch request content and header, default timeout set to 300sec
        """
        try:
            url = target
            if parameters:
                url = f'{target}?{urlencode(parameters)}'
            if user:
                response = requests.get(
                    url,
                    headers=headers or {},
                    auth=(user, password),
                    timeout=timeout
                )
            else:
                response = requests.get(url, headers=headers or {})
            result = json.loads(response.content)
            result.update(response.headers)
            return result
        except requests.exceptions.Timeout:
            raise CgyleRequestError(
                f'Request to {url} timed out'
            )
        except Exception as issue:
            raise CgyleRequestError(
                f'Failed to fetch request data: {issue}'
            )
