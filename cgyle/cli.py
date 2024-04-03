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
           [--apply]
           [--filter=<expression>]
           [--registry-creds=<user:pwd>]
           [--store-oci-archive=<dir>]
           [--tls-verify-proxy=<BOOL>]
           [--tls-verify-registry=<BOOL>]

options:
    --apply
        Apply the cache update

    --filter=<expression>
        Apply given regular expression on the list of
        containers received from the registry

    --from=<registry>
        Registry location to read the catalog of containers
        from. It is expected that the referenced proxy registry
        uses this location in its configuration

    --registry-creds=<user:pwd>
        Contact given registry with the provided credentials

    --store-oci-archive=<dir>
        Store each container as oci archive below the given
        directory

    --tls-verify-proxy=BOOL
        Contact given proxy location without TLS [default: True]

    --tls-verify-registry=BOOL
        Contact given registry location without TLS [default: True]

    --updatecache=<proxy>
        Proxy location to trigger the cache update for. If
        the special value local://distribution:DIR is set, a local
        distribution registry will be started as a proxy and
        its cache is stored below the given directory DIR
"""
import re
import time
import threading
import logging
from typing import (
    List, Dict
)
from docopt import docopt
from contextlib import ExitStack

from cgyle.version import __version__
from cgyle.proxy import DistributionProxy
from cgyle.catalog import Catalog

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
        self.threads: Dict[str, threading.Thread] = {}
        self.tls_proxy = \
            True if self.arguments['--tls-verify-proxy'] == 'True' else False
        self.tls_registry = \
            True if self.arguments['--tls-verify-registry'] == 'True' else False
        self.tls_registry_creds = self.arguments['--registry-creds'] or ''
        self.dryrun = not bool(self.arguments['--apply'])
        self.cache = self.arguments['--updatecache']
        self.pattern = self.arguments['--filter']
        self.from_registry = self.arguments['--from']
        self.store_oci_archive = self.arguments['--store-oci-archive'] or ''

        self.local_distribution_cache = ''
        if self.cache.startswith('local://distribution'):
            self.local_distribution_cache = self.cache.split(':')[2]

        self.use_podman_search = False
        if self.tls_registry_creds or self.tls_registry:
            self.use_podman_search = True

        if process:
            if self.cache:
                self.update_cache()

    def update_cache(self) -> None:
        count = 0
        request_count = 0

        with ExitStack() as main:
            if self.local_distribution_cache and not self.dryrun:
                # local instance for cache setup requested
                local_proxy = DistributionProxy(self.cache)
                main.push(local_proxy)
                self.tls_proxy = False
                self.cache = local_proxy.create_local_distribution_instance(
                    data_dir=self.local_distribution_cache,
                    remote=self.from_registry,
                    proxy_creds=self.tls_registry_creds
                )

            with ExitStack() as stack:
                # process container fetch requests...
                if self.dryrun:
                    logging.info(f'Proxy: [{self.cache}]:')
                for container in self._get_catalog():
                    if not self._filter_ok(container):
                        continue
                    count += 1
                    if self.dryrun:
                        logging.info(f'  ({count}) - {container}')
                    else:
                        request_count += 1
                        while request_count >= self.max_requests:
                            stack.pop_all().close()
                            request_count = self._get_running_requests()
                            if request_count >= self.max_requests:
                                time.sleep(self.wait_timeout)

                        proxy = DistributionProxy(self.cache, container)
                        stack.push(proxy)

                        proxy_thread = threading.Thread(
                            target=proxy.update_cache,
                            kwargs={
                                'tls_verify': self.tls_proxy,
                                'store_oci_archive': self.store_oci_archive
                            }
                        )
                        proxy_thread.start()
                        self.threads[format(count)] = proxy_thread

            if not self.dryrun:
                # wait until all requests are processed
                request_count = self._get_running_requests()
                while request_count > 0:
                    time.sleep(self.wait_timeout)
                    request_count = self._get_running_requests()

    def _get_running_requests(self):
        threads_done = []
        for count in self.threads:
            if not self.threads[count].is_alive():
                threads_done.append(count)
        for count in threads_done:
            del self.threads[count]
        return len(self.threads.keys())

    def _get_catalog(self) -> List[str]:
        catalog = Catalog()
        if self.use_podman_search:
            return catalog.get_catalog_podman_search(
                self.from_registry, self.tls_registry,
                self.tls_registry_creds
            )
        else:
            return catalog.get_catalog(self.from_registry)

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
