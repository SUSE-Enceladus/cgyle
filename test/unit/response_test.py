from unittest.mock import (
    patch, Mock
)
from pytest import raises
from cgyle.response import Response
from cgyle.exceptions import CgyleJsonError


class TestResponse:
    def setup(self):
        self.response = Response()

    def setup_method(self, cls):
        self.setup()

    @patch('cgyle.response.requests')
    def test_get(self, mock_requests):
        response = Mock()
        response.content = b'{"repositories": ["name"]}'
        mock_requests.request.return_value = response
        assert self.response.get(
            'https://registry.opensuse.org/v2/_catalog'
        ) == {'repositories': ['name']}

    @patch('cgyle.response.requests')
    def test_get_catalog(self, mock_requests):
        response = Mock()
        response.content = b'{"repositories": ["name"]}'
        mock_requests.request.return_value = response
        assert self.response.get_catalog(
            'https://registry.opensuse.org/v2/_catalog'
        ) == ['name']

    @patch('cgyle.response.requests')
    def test_get_raises(self, mock_requests):
        response = Mock()
        response.content = b'foo'
        mock_requests.request.return_value = response
        with raises(CgyleJsonError):
            self.response.get('location')
