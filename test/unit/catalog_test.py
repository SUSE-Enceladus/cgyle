from unittest.mock import patch
from pytest import raises
from cgyle.catalog import Catalog
from cgyle.exceptions import CgyleCatalogError


class TestCatalog:
    def setup(self):
        self.catalog = Catalog()

    def setup_method(self, cls):
        self.setup()

    @patch('cgyle.catalog.Response.get')
    def test_get_catalog(self, mock_Response_get):
        mock_Response_get.return_value = {'repositories': ['name']}
        assert self.catalog.get_catalog(
            'https://registry.opensuse.org/v2/_catalog'
        ) == ['name']

    @patch('cgyle.catalog.Response.get')
    def test_get_catalog_raises(self, mock_Response_get):
        mock_Response_get.return_value = {'errors': ['some']}
        with raises(CgyleCatalogError):
            self.catalog.get_catalog(
                'https://registry.opensuse.org/v2/_catalog'
            )
