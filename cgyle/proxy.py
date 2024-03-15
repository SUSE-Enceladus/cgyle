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
import logging
import subprocess
from typing import Optional
from cgyle.exceptions import CgyleCommandError


class DistributionProxy:
    """
    Access methods for the distribution registry
    configured as proxy
    """
    def __init__(self, server: str, container: str) -> None:
        self.server = server
        self.conftainer = container
        self.skopeo: Optional[subprocess.Popen[bytes]] = None
        self.pid = 0

    def __enter__(self):
        return self

    def update_cache(
        self, tag: str = 'latest', tls_verify: bool = True,
        blocking: bool = True
    ) -> None:
        """
        Trigger a cache update of the container
        """
        call_args = [
            'skopeo', 'copy',
            f'--src-tls-verify={format(tls_verify).lower()}',
            f'docker://{self.server}/{self.conftainer}:{tag}',
            f'oci-archive:/dev/null:{tag}'
        ]
        try:
            self.skopeo = subprocess.Popen(
                call_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.pid = self.skopeo.pid
            if blocking:
                self.skopeo.communicate()
        except Exception as issue:
            raise CgyleCommandError(
                'Failed to update cache for: {}: {}'.format(
                    self.conftainer, issue
                )
            )

    def get_pid(self) -> str:
        return format(self.pid)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type == KeyboardInterrupt:
            if self.pid > 0:
                os.kill(self.pid, 15)
        elif self.skopeo:
            # prevent becoming a zombie
            self.skopeo.wait()
            # print error information if present
            error = self.skopeo.stderr.read()
            if error:
                logging.error(f'[{self.pid}]: {error}')
