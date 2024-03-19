from unittest.mock import (
    patch, Mock
)
from pytest import raises
from cgyle.catalog import Catalog
from cgyle.exceptions import (
    CgyleCatalogError,
    CgylePodmanError,
    CgyleCommandError
)


class TestCatalog:
    def setup(self):
        self.catalog = Catalog()

    def setup_method(self, cls):
        self.setup()

    @patch('cgyle.catalog.Response.get')
    def test_get_catalog(self, mock_Response_get):
        mock_Response_get.return_value = {'repositories': ['name']}
        assert self.catalog.get_catalog(
            'https://registry.opensuse.org'
        ) == ['name']

    @patch('cgyle.catalog.Response.get')
    def test_get_catalog_raises(self, mock_Response_get):
        mock_Response_get.return_value = {'errors': ['some']}
        with raises(CgyleCatalogError):
            self.catalog.get_catalog(
                'https://registry.opensuse.org'
            )

    @patch('cgyle.proxy.subprocess.Popen')
    def test_get_catalog_podman_search_raises_with_error(self, mock_Popen):
        podman = Mock()
        podman.communicate.return_value = (b'output', b'error')
        mock_Popen.return_value = podman
        with raises(CgylePodmanError):
            self.catalog.get_catalog_podman_search(
                'https://registry.opensuse.org'
            )

    @patch('cgyle.proxy.subprocess.Popen')
    def test_get_catalog_podman_search_raises(self, mock_Popen):
        mock_Popen.side_effect = Exception
        with raises(CgyleCommandError):
            self.catalog.get_catalog_podman_search(
                'https://registry.opensuse.org'
            )

    @patch('cgyle.proxy.subprocess.Popen')
    def test_get_catalog_podman_search(self, mock_Popen):
        podman = Mock()
        podman.communicate.return_value = (b'server/A\nserver/B', b'')
        mock_Popen.return_value = podman
        assert self.catalog.get_catalog_podman_search(
            'https://registry.opensuse.org'
        ) == ['A', 'B']
