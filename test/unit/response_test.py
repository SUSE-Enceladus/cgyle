import requests
from unittest.mock import patch
from pytest import raises
from cgyle.response import Response
from cgyle.exceptions import CgyleRequestError


class TestResponse:
    def setup(self):
        self.response = Response()

    def setup_method(self, cls):
        self.setup()

    @patch.object(Response, 'fetch')
    def test_get_auth_challenge(self, mock_fetch):
        mock_fetch.return_value = {
            'www-authenticate': 'Bearer realm="some"'
        }
        assert self.response.get_auth_challenge('some') == 'Bearer realm="some"'

    def test_extract_bearer_parameters(self):
        challenge = 'Bearer realm="some",service="some"'
        assert self.response.extract_bearer_parameters(
            challenge
        ) == ('some', 'some')

    @patch('cgyle.response.requests.get')
    def test_fetch(self, mock_requests_get):
        mock_requests_get.return_value.content = '{"content": "value"}'
        mock_requests_get.return_value.headers = {'header': 'some'}
        self.response.fetch(
            'some_url', user='user', password='pass'
        )
        mock_requests_get.assert_called_with(
            'some_url', headers={}, auth=('user', 'pass'), timeout=300
        )
        assert self.response.fetch(
            'some_url', parameters={'some': 'value'}
        ) == {
            'content': 'value',
            'header': 'some'
        }

    @patch('cgyle.response.requests.get')
    def test_fetch_raises_on_request_handling(self, mock_requests_get):
        mock_requests_get.side_effect = Exception
        with raises(CgyleRequestError):
            self.response.fetch('some_url')

    @patch('cgyle.response.requests.get')
    def test_fetch_raises_on_timeout(self, mock_requests_get):
        mock_requests_get.side_effect = requests.exceptions.Timeout
        with raises(CgyleRequestError):
            self.response.fetch('some_url')
