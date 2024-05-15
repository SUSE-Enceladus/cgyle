import logging
import sys
from cgyle.cli import Cli
from unittest.mock import (
    patch, Mock, call
)
from pytest import (
    fixture, raises
)
from cgyle.exceptions import CgyleThreadError

from .test_helper import (
    argv_cgyle_tests, argv_cgyle_list_archs
)


class TestCli:
    @fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def setup(self):
        sys.argv = argv_cgyle_tests
        self.cli = Cli(process=False)

    def setup_method(self, cls):
        self.setup()

    def test_list_archs(self):
        sys.argv = argv_cgyle_list_archs
        with self._caplog.at_level(logging.INFO):
            Cli()
            assert "['amd64', 'x86_64', 'arm64', 'aarch64', 's390x', 'ppc64el', 'ppc64le']" in self._caplog.text

    @patch.object(Cli, 'update_cache')
    def test_process(self, mock_update_cache):
        Cli()
        mock_update_cache.assert_called_once_with()

    @patch('cgyle.cli.Catalog')
    def test_update_cache_with_filter(self, mock_Catalog):
        catalog = Mock()
        catalog.get_catalog.return_value = ['some-container']
        catalog.apply_filter.return_value = ['some-container']
        catalog.translate_policy.return_value = []
        mock_Catalog.return_value = catalog
        self.cli.use_podman_search = False
        self.cli.dryrun = True
        self.cli.pattern = '.*'
        self.cli.policy = '../data/policy'
        self.cli.update_cache()
        assert catalog.apply_filter.call_args_list == [
            call(['some-container'], []),
            call(['some-container'], ['.*'])
        ]
        catalog.translate_policy.assert_called_once_with(
            '../data/policy', [], []
        )

    @patch.object(Cli, '_get_catalog')
    def test_update_cache_dry_run(self, mock_get_catalog):
        mock_get_catalog.return_value = ['some-container']
        self.cli.dryrun = True
        with self._caplog.at_level(logging.INFO):
            self.cli.update_cache()
            assert 'some-container' in self._caplog.text

    @patch.object(Cli, '_get_catalog')
    @patch('cgyle.cli.DistributionProxy')
    def test_update_cache(
        self, mock_DistributionProxy, mock_get_catalog
    ):
        proxy = Mock()
        mock_DistributionProxy.return_value = proxy

        mock_get_catalog.return_value = ['some-container']
        self.cli.dryrun = False
        self.cli.local_distribution_cache = 'local://distribution:some'
        self.cli.max_requests = 1
        with self._caplog.at_level(logging.INFO):
            self.cli.update_cache()
            assert mock_DistributionProxy.call_args_list == [
                call('local://distribution:some'),
                call(
                    proxy.create_local_distribution_instance.return_value,
                    'some-container'
                )
            ]
            proxy.create_local_distribution_instance.assert_called_once_with(
                data_dir='local://distribution:some',
                remote='registry.opensuse.org',
                proxy_creds=''
            )
            proxy.update_cache.assert_called_once_with(
                'registry.opensuse.org', False, '', '', []
            )

    @patch.object(Cli, '_get_catalog')
    @patch('concurrent.futures.as_completed')
    def test_update_cache_thread_raises(
        self, mock_futures_as_completed,
        mock_get_catalog
    ):
        mock_get_catalog.return_value = ['some-container']
        self.cli.dryrun = False
        self.cli.local_distribution_cache = None
        worker = Mock()
        worker.exception = Mock(return_value='error')
        mock_futures_as_completed.return_value = [worker]

        with raises(CgyleThreadError):
            self.cli.update_cache()

    @patch('cgyle.cli.Catalog')
    def test_get_catalog_request(self, mock_Catalog):
        catalog = Mock()
        mock_Catalog.return_value = catalog
        self.cli.use_podman_search = False
        self.cli._get_catalog()
        catalog.get_catalog.assert_called_once_with(
            'registry.opensuse.org'
        )

    @patch('cgyle.cli.Catalog')
    def test_get_catalog_podman_search(self, mock_Catalog):
        catalog = Mock()
        mock_Catalog.return_value = catalog
        self.cli.use_podman_search = True
        self.cli._get_catalog()
        catalog.get_catalog_podman_search.assert_called_once_with(
            'registry.opensuse.org', True, ''
        )
