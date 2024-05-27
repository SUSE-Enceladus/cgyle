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
from typing import List

from cgyle.exceptions import CgyleCredentialsError


class Credentials:
    """
    Methods to handle credential sources
    """
    @staticmethod
    def read(credentials_or_file: str) -> List[str]:
        if os.path.isfile(credentials_or_file):
            return Credentials.get_from_file(credentials_or_file)
        return Credentials.get_credentials(credentials_or_file)

    @staticmethod
    def get_credentials(creds: str) -> List[str]:
        try:
            username, password = creds.split(':') if creds else ['', '']
        except ValueError:
            raise CgyleCredentialsError(
                f'Invalid credentials, expected user:pass, got {creds}'
            )
        return [username, password]

    @staticmethod
    def get_from_file(filename: str) -> List[str]:
        """
        Read credentials from the given filename. It is expected that
        the file is a yaml file containing the following information:

        .. code:: yaml

           scc:
             username: user
             password: pass
        """
        try:
            with open(filename) as data:
                config = yaml.safe_load(data)
                return [config['scc']['username'], config['scc']['password']]
        except Exception as issue:
            raise CgyleCredentialsError(
                f'Failed reading credentials from {filename}: {issue}'
            )
