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
           [--arch=<arch>...]
           [--registry-creds=<user:pwd>]
           [--proxy-creds=<user:pwd>]
           [--store-oci=<dir>|--push-oci=<repo> --push-oci-creds=<user:pwd>]
           [--tls-verify-proxy=<BOOL>]
           [--tls-verify-registry=<BOOL>]
           [--max-requests=<number>]
           [--remove-signatures]
       cgyle --list-archs

options:
    --apply
        Apply the cache update

    --arch=<arch>...
        Select architecture from multiarch containers as well
        as from policy paths.

    --list-archs
        List available arch names that cgyle can match

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

    --registry-creds=<user:pwd|filename>
        Contact given registry with the provided credentials.

    --proxy-creds=<user:pwd|filename>
        Login to given proxy registry with the provided credentials
        using podman login

    --store-oci=<dir>
        Store each container as oci dir below the given
        directory

    --push-oci=<repo>
        Push each container to the given repository.
        this will push each container as containerbasename-tagname-arch
        into the given repository

    --push-oci-creds=<user:pwd>
        Contact given push-oci registry with the provided credentials

    --remove-signatures
        Do not copy signatures. Necessary when copying a signed image
        to a destination which does not support signatures

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
import os
import concurrent.futures
import logging
from typing import List
from docopt import docopt
from contextlib import ExitStack

from cgyle.version import __version__
from cgyle.proxy import DistributionProxy
from cgyle.catalog import Catalog

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
        self.list_archs = self.arguments['--list-archs']
        self.pattern = self.arguments['--filter']
        self.policy = self.arguments['--filter-policy']
        self.use_archs: List[str] = self.arguments['--arch']
        self.policy_skip_sections: List[str] = \
            self.arguments['--skip-policy-section']
        self.from_registry = self.arguments['--from']
        self.store_oci = self.arguments['--store-oci'] or ''
        self.push_oci = self.arguments['--push-oci'] or ''
        self.tls_push_oci_creds = self.arguments['--push-oci-creds'] or ''
        self.remove_signatures = bool(self.arguments['--remove-signatures'])
        self.catalog: List[str] = []

        self.local_distribution_cache = ''
        if self.cache and self.cache.startswith('local://distribution'):
            self.local_distribution_cache = self.cache.split(':')[2]

        self.use_podman_search = False
        if self.tls_registry_creds or self.tls_registry:
            self.use_podman_search = True

        if process:
            if self.list_archs:
                logging.info(Catalog.get_arch_list())
            elif self.cache:
                self.update_cache()

    def update_cache(self) -> None:
        count = 0
        self.catalog = []

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
                                self.from_registry,
                                self.tls_proxy,
                                self.store_oci,
                                self.push_oci,
                                self.tls_push_oci_creds,
                                self.tls_proxy_creds,
                                self.use_archs,
                                self.remove_signatures
                            )
                        )

            thread_executor.shutdown(wait=False)
            if not self.dryrun:
                # wait until all requests are processed
                for worker in concurrent.futures.as_completed(thread_pool):
                    exception = worker.exception()
                    if exception is not None:
                        logging.error(f'Thread failed with: {exception}')

        # All done, collect errors if any. cgyle only keeps the
        # log files of failed caching attempts and wipes the successful
        # ones because there is no meaningful information in a successful
        # caching process other than, the container was cached, which
        # is an information that is still present by reading the log
        # directory tree. The error information from all failed log
        # files is now combined into one log file and appended to an
        # eventually existing log file.
        if not self.dryrun:
            log_path = DistributionProxy.get_log_path()
            log_file_name = f'{log_path}.log'
            try:
                with open(log_file_name, 'a') as collect_fd:
                    for topdir, dirs, files in sorted(os.walk(log_path)):
                        for entry in sorted(dirs + files):
                            if entry in files:
                                logfile = os.sep.join([topdir, entry])
                                if logfile.endswith('.log'):
                                    if any(container_name in logfile.lstrip(os.sep) for container_name in self.catalog):
                                        collect_fd.write(f'{logfile}:{os.linesep}')
                                        with open(logfile) as log_fd:
                                            collect_fd.write(
                                                log_fd.read() or 'no log data'
                                            )
                                            collect_fd.write(os.linesep)
            except IOError as issue:
                logging.error(f'Failed to create logfile: {issue}')

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
                    self.policy, self.policy_skip_sections, self.use_archs
                )
            )

        if self.pattern:
            result = catalog.apply_filter(result, [self.pattern])

        for entry in result:
            self.catalog.append(entry.lstrip(os.sep))

        return result
