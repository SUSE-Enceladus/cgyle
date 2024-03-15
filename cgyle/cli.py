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
"""
usage: cgyle -h | --help
       cgyle --updatecache=<proxy> --from=<registry>
           [--filter=<expression>]
           [--dry-run]
           [--no-tls-verify]

options:
    --updatecache=<proxy>
        Proxy location to trigger the cache update for

    --from=<registry>
        Registry location to read the catalog of containers
        from. It is expected that the referenced proxy registry
        uses this location in its configuration

    --filter=<expression>
        Apply given regular expression on the list of
        containers received from the registry

    --no-tls-verify
        Don't require HTTPS

    --dry-run
        Only print what would happen
"""
import re
import time
import logging
from typing import (
    List, Dict
)
from docopt import docopt
from contextlib import ExitStack
import psutil

from cgyle.version import __version__
from cgyle.proxy import DistributionProxy
from cgyle.response import Response

from cgyle.exceptions import CgyleFilterExpressionError

logging.basicConfig(
    format='%(levelname)s:%(message)s',
    level=logging.DEBUG
)


class Cli:
    """
    Implements the command line interface
    """
    def __init__(self, process: bool = True) -> None:
        self.arguments = docopt(
            __doc__,
            version='cgyle version ' + __version__,
            options_first=True
        )

        self.max_requests = 10
        self.wait_timeout = 3
        self.pids: Dict[str, int] = {}
        self.tls = False if self.arguments['--no-tls-verify'] else True
        self.dryrun = bool(self.arguments['--dry-run'])
        self.cache = self.arguments['--updatecache']
        self.pattern = self.arguments['--filter']

        if process:
            if self.cache:
                self.update_cache()

    def update_cache(self) -> None:
        count = 0
        request_count = 0
        with ExitStack() as stack:
            for container in self._get_catalog():
                if not self._filter_ok(container):
                    continue
                count += 1
                if self.dryrun:
                    logging.info(
                        '({}): Requesting Cache Update for: {} at {}'.format(
                            count, container, self.cache
                        )
                    )
                else:
                    request_count += 1
                    while request_count >= self.max_requests:
                        stack.pop_all().close()
                        request_count = self._get_running_requests()
                        if request_count >= self.max_requests:
                            time.sleep(self.wait_timeout)

                    proxy = DistributionProxy(self.cache, container)
                    stack.push(proxy)
                    proxy.update_cache(
                        tls_verify=self.tls, blocking=False
                    )
                    self.pids[proxy.get_pid()] = 1
                    logging.info(
                        '[{}]: Processing Cache Update for: {} at {}'.format(
                            proxy.get_pid(), container, self.cache
                        )
                    )

        # wait until all requests are processed
        if not self.dryrun:
            request_count = self._get_running_requests()
            while request_count > 0:
                time.sleep(self.wait_timeout)
                request_count = self._get_running_requests()

    def _get_running_requests(self):
        pids_to_delete = []
        for pid in self.pids:
            if not psutil.pid_exists(int(pid)):
                logging.info(f'[{pid}]: Cache Update done')
                pids_to_delete.append(pid)
        for pid in pids_to_delete:
            del self.pids[pid]
        return len(self.pids.keys())

    def _get_catalog(self) -> List[str]:
        response = Response()
        return response.get_catalog(self.arguments['--from'])

    def _filter_ok(self, data: str) -> bool:
        if self.pattern:
            try:
                if re.match(self.pattern, data):
                    return True
                else:
                    return False
            except Exception as issue:
                raise CgyleFilterExpressionError(
                    f'Invalid expression [{self.pattern}]: {issue}'
                )
        return True
