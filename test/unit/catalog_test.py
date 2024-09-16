from unittest.mock import (
    patch, Mock
)
from pytest import raises
from cgyle.catalog import Catalog
from cgyle.exceptions import (
    CgyleCatalogError,
    CgylePodmanError,
    CgyleCommandError,
    CgyleFilterExpressionError
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

    @patch('time.sleep')
    @patch('cgyle.proxy.subprocess.Popen')
    def test_get_catalog_podman_search_raises_with_error(self, mock_Popen, mock_time):
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

    @patch('time.sleep')
    @patch('cgyle.proxy.subprocess.Popen')
    def test_get_catalog_podman_search(self, mock_Popen, mock_time):
        podman = Mock()
        podman.communicate.return_value = (b'server/A\nserver/B', b'')
        mock_Popen.return_value = podman
        assert self.catalog.get_catalog_podman_search(
            'https://registry.opensuse.org', True, 'user:pwd'
        ) == ['A', 'B']
        mock_Popen.assert_called_once_with(
            [
                'podman', 'search', '--tls-verify=true',
                '--limit', '2147483647', '--creds', 'user:pwd',
                'registry.opensuse.org:/'
            ], stdout=-1, stderr=-1
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
