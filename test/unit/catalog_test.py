from unittest.mock import patch
from pytest import raises
from cgyle.catalog import Catalog
from cgyle.response import Response
from cgyle.exceptions import (
    CgyleError,
    CgyleCatalogError,
    CgyleFilterExpressionError
)


class TestCatalog:
    def setup(self):
        self.catalog = Catalog()

    def setup_method(self, cls):
        self.setup()

    @patch.object(Response, 'get_auth_challenge')
    @patch.object(Response, 'extract_bearer_parameters')
    @patch.object(Response, 'fetch')
    def test_get_catalog(
        self,
        mock_fetch,
        mock_extract_bearer_parameters,
        mock_get_auth_challenge
    ):
        def fetch(
            target, parameters=None, headers=None, user='', password=''
        ):
            if 'some_link' in target:
                return {}
            else:
                return {
                    'repositories': ['name'],
                    'token': 'some',
                    'Link': 'some_link'
                }

        mock_extract_bearer_parameters.return_value = ('realm', 'service')
        mock_get_auth_challenge.return_value = 'some'
        mock_fetch.side_effect = fetch
        assert self.catalog.get_catalog(
            'https://registry.opensuse.org', 'user:pass'
        ) == ['name', 'name']

    @patch.object(Response, 'get_auth_challenge')
    @patch.object(Response, 'extract_bearer_parameters')
    @patch.object(Response, 'fetch')
    def test_get_catalog_raises(
        self,
        mock_fetch,
        mock_extract_bearer_parameters,
        mock_get_auth_challenge
    ):
        mock_get_auth_challenge.return_value = 'some'
        mock_extract_bearer_parameters.return_value = ('', '')
        with raises(CgyleCatalogError):
            self.catalog.get_catalog(
                'https://registry.opensuse.org'
            )
        mock_extract_bearer_parameters.reset_mock()
        mock_extract_bearer_parameters.return_value = ('realm', 'service')
        mock_fetch.return_value = {
            'token': None
        }
        with raises(CgyleCatalogError):
            self.catalog.get_catalog(
                'https://registry.opensuse.org'
            )
        mock_get_auth_challenge.return_value = None
        mock_fetch.return_value = {
            'errors': 'some'
        }
        with raises(CgyleCatalogError):
            self.catalog.get_catalog(
                'https://registry.opensuse.org'
            )

    def test_apply_filter_raises(self):
        with raises(CgyleFilterExpressionError):
            self.catalog.apply_filter(['entry'], ['*'])

    def test_apply_filter(self):
        assert self.catalog.apply_filter(
            ['suse/foo/bar', 'bcl/xxx'], [r'.*bcl.*']
        ) == ['bcl/xxx']

    def test_apply_policy(self):
        assert self.catalog.apply_filter(
            [
                'foo/bar/foobar',
                'foo/bar',
                'sles/more/things',
                'sles/moresuper/sles',
                'extra_repo',
                'bar',
                'bat',
                'bar/foo',
                'sles',
                'suse/manager/proxy-aarch64',
                'suse/manager/server-aarch64',
                'suse/manager/proxy-ppc64le',
                'suse/manager/server-ppc64le',
                'suse/manager/proxy-x86_64',
                'suse/manager/server-x86_64'
            ],
            self.catalog.translate_policy('../data/policy.test')
        ) == [
            'bar',
            'foo/bar',
            'sles',
            'sles/more/things',
            'sles/moresuper/sles',
            'suse/manager/proxy-x86_64',
            'suse/manager/server-x86_64'
        ]

    def test_translate_policy(self):
        assert self.catalog.translate_policy(
            '../data/policy', use_archs=['x86_64']
        ) == [
            '^[^/]*$',
            '^bci/.*$',
            '^suse/[^/]*$',
            '^foo/[^/]*/bar/.*$',
            '^foo/[^/]*/x86_64/bar/.*$'
        ]
        assert self.catalog.translate_policy(
            '../data/policy'
        ) == [
            '^[^/]*$',
            '^bci/.*$',
            '^suse/[^/]*$',
            '^foo/[^/]*/bar/.*$',
            '^foo/[^/]*/x86_64/bar/.*$',
            '^foo/s390x/bar$'
        ]

    def test_translate_policy_open_failed(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.side_effect = Exception
            with raises(CgyleError):
                self.catalog.translate_policy('bogus', use_archs=['x86_64'])

    def test_get_tag_filter(self):
        assert self.catalog.get_tag_filter(
            '../data/policy'
        ) == {
            'bci/**': '^(?!16.1)'
        }
        assert self.catalog.get_tag_filter(
            '../data/policy.test'
        ) == {}

    def test_get_tag_filter_open_failed(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.side_effect = Exception
            with raises(CgyleError):
                self.catalog.get_tag_filter('bogus')
