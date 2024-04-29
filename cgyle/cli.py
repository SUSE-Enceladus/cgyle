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
           [--filter-policy=<policyfile>|(--filter-policy=<policyfile> --skip-policy-section=<name>...)]
           [--registry-creds=<user:pwd>]
           [--proxy-creds=<user:pwd>]
           [--store-oci=<dir>]
           [--tls-verify-proxy=<BOOL>]
           [--tls-verify-registry=<BOOL>]
           [--max-requests=<number>]

options:
    --apply
        Apply the cache update

    --filter=<expression>
        Apply given regular expression on the list of
        containers received from the registry

    --filter-policy=<policyfile>
        Apply rules provided in the policyfile on the
        list of containers received from the registry

    --skip-policy-section=<name>...
        Skip the provided section name from the policyfile.
        This option can be specified multiple times.

    --from=<registry>
        Registry location to read the catalog of containers
        from. It is expected that the referenced proxy registry
        uses this location in its configuration

    --registry-creds=<user:pwd>
        Contact given registry with the provided credentials

    --proxy-creds=<user:pwd>
        Login to given proxy registry with the provided credentials
        using podman login

    --store-oci=<dir>
        Store each container as oci dir below the given
        directory

    --tls-verify-proxy=BOOL
        Contact given proxy location without TLS [default: True]

    --tls-verify-registry=BOOL
        Contact given registry location without TLS [default: True]

    --max-requests=<number>
        Maximum number of parallel container requests. Note, all
        container tags are handled in one request [default: 10]

    --updatecache=<proxy>
        Proxy location to trigger the cache update for. If
        the special value local://distribution:DIR is set, a local
        distribution registry will be started as a proxy and
        its cache is stored below the given directory DIR
"""
import concurrent.futures
import logging
from typing import List
from docopt import docopt
from contextlib import ExitStack

from cgyle.version import __version__
from cgyle.proxy import DistributionProxy
from cgyle.catalog import Catalog
from cgyle.exceptions import CgyleThreadError

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
        self.max_requests = int(self.arguments['--max-requests'])
        self.tls_proxy = \
            True if self.arguments['--tls-verify-proxy'] == 'True' else False
        self.tls_registry = \
            True if self.arguments['--tls-verify-registry'] == 'True' else False
        self.tls_registry_creds = self.arguments['--registry-creds'] or ''
        self.tls_proxy_creds = self.arguments['--proxy-creds'] or ''
        self.dryrun = not bool(self.arguments['--apply'])
        self.cache = self.arguments['--updatecache']
        self.pattern = self.arguments['--filter']
        self.policy = self.arguments['--filter-policy']
        self.policy_skip_sections: List[str] = \
            self.arguments['--skip-policy-section']
        self.from_registry = self.arguments['--from']
        self.store_oci = self.arguments['--store-oci'] or ''

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

            thread_pool = []
            thread_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_requests
            )
            with ExitStack() as stack:
                # process container fetch requests...
                if self.dryrun:
                    logging.info(f'Proxy: [{self.cache}]:')
                for container in self._get_catalog():
                    count += 1
                    if self.dryrun:
                        logging.info(f'  ({count}) - {container}')
                    else:
                        proxy = DistributionProxy(self.cache, container)
                        stack.push(proxy)
                        thread_pool.append(
                            thread_executor.submit(
                                proxy.update_cache,
                                DistributionProxy(
                                    self.from_registry, container
                                ).get_tags(),
                                self.tls_proxy,
                                self.store_oci,
                                self.tls_proxy_creds
                            )
                        )

            thread_executor.shutdown(wait=False)
            if not self.dryrun:
                # wait until all requests are processed
                for worker in concurrent.futures.as_completed(thread_pool):
                    exception = worker.exception()
                    if exception is not None:
                        raise CgyleThreadError(exception)

    def _get_catalog(self) -> List[str]:
        catalog = Catalog()
        if self.use_podman_search:
            result = catalog.get_catalog_podman_search(
                self.from_registry, self.tls_registry,
                self.tls_registry_creds
            )
        else:
            result = catalog.get_catalog(self.from_registry)

        if self.policy:
            result = catalog.apply_filter(
                result, catalog.translate_policy(
                    self.policy, self.policy_skip_sections
                )
            )

        if self.pattern:
            result = catalog.apply_filter(result, [self.pattern])

        return result
