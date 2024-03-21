import logging
from cgyle.cli import Cli
from unittest.mock import (
    patch, Mock
)
from pytest import (
    raises, fixture
)
from cgyle.exceptions import CgyleFilterExpressionError

from .test_helper import argv_cgyle_tests


class TestCli:
    @fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def setup(self):
        self.argv = argv_cgyle_tests
        self.cli = Cli(process=False)

    def setup_method(self, cls):
        self.setup()

    @patch.object(Cli, 'update_cache')
    def test_process(self, mock_update_cache):
        Cli()
        mock_update_cache.assert_called_once_with()

    @patch.object(Cli, '_filter_ok')
    @patch.object(Cli, '_get_catalog')
    def test_update_cache_all_filtered(self, mock_get_catalog, mock_filter_ok):
        mock_get_catalog.return_value = ['some-container']
        mock_filter_ok.return_value = False
        self.cli.update_cache()
        mock_filter_ok.assert_called_once_with('some-container')

    @patch.object(Cli, '_filter_ok')
    @patch.object(Cli, '_get_catalog')
    def test_update_cache_dry_run(self, mock_get_catalog, mock_filter_ok):
        mock_get_catalog.return_value = ['some-container']
        mock_filter_ok.return_value = True
        self.cli.dryrun = True
        with self._caplog.at_level(logging.INFO):
            self.cli.update_cache()
            assert 'some-container' in self._caplog.text

    @patch.object(Cli, '_filter_ok')
    @patch.object(Cli, '_get_catalog')
    @patch.object(Cli, '_get_running_requests')
    @patch('cgyle.cli.DistributionProxy')
    @patch('time.sleep')
    def test_update_cache(
        self, mock_time_sleep, mock_DistributionProxy,
        mock_get_running_requests, mock_get_catalog, mock_filter_ok
    ):
        pids = [2, 0, 2, 0]
        proxy = Mock()
        mock_DistributionProxy.return_value = proxy

        def get_running_requests(*args):
            return pids.pop(0)

        mock_get_running_requests.side_effect = get_running_requests
        mock_get_catalog.return_value = ['some-container']
        mock_filter_ok.return_value = True
        self.cli.dryrun = False
        self.cli.max_requests = 1
        with self._caplog.at_level(logging.INFO):
            self.cli.update_cache()
            mock_DistributionProxy.assert_called_once_with(
                'localhost:5000', 'some-container'
            )
            proxy.update_cache.assert_called_once_with(
                tls_verify=True
            )

    def test_get_running_requests(self):
        thread = Mock()
        thread.is_alive.return_value = False
        self.cli.threads = {'1': thread}
        assert self.cli._get_running_requests() == 0

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

    def test_filter_ok(self):
        self.cli.pattern = '.*'
        assert self.cli._filter_ok('data') is True
        self.cli.pattern = 'xxx'
        assert self.cli._filter_ok('data') is False
        self.cli.pattern = '*'
        with raises(CgyleFilterExpressionError):
            self.cli._filter_ok('data')
        self.cli.pattern = None
        assert self.cli._filter_ok('data') is True
