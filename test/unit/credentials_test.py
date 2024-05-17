from unittest.mock import patch
from pytest import raises
from cgyle.credentials import Credentials
from cgyle.exceptions import CgyleCredentialsError


class TestCredentials:
    @patch('os.path.isfile')
    def test_get_credentials_from_string(self, mock_os_path_isfile):
        mock_os_path_isfile.return_value = False
        assert Credentials.read('user:pass') == ['user', 'pass']

    @patch('os.path.isfile')
    def test_get_credentials_from_file(self, mock_os_path_isfile):
        mock_os_path_isfile.return_value = True
        assert Credentials.read('../data/credentials') == ['user', 'pass']

    @patch('os.path.isfile')
    def test_get_credentials_from_string_invalid(self, mock_os_path_isfile):
        mock_os_path_isfile.return_value = False
        with raises(CgyleCredentialsError):
            Credentials.read('bogus')

    @patch('os.path.isfile')
    def test_get_credentials_from_file_invalid(self, mock_os_path_isfile):
        mock_os_path_isfile.return_value = True
        with raises(CgyleCredentialsError):
            Credentials.read('not_a_file')
