from unittest.mock import (
    patch, Mock
)
from pytest import raises
from cgyle.proxy import DistributionProxy
from cgyle.exceptions import CgyleCommandError


class TestDistributionProxy:
    def setup(self):
        self.proxy = DistributionProxy('server', 'container')

    def setup_method(self, cls):
        self.setup()

    @patch('cgyle.proxy.subprocess.Popen')
    def test_update_cache_raises(self, mock_Popen):
        mock_Popen.side_effect = Exception
        with raises(CgyleCommandError):
            self.proxy.update_cache()

    @patch('cgyle.proxy.subprocess.Popen')
    def test_update_cache(self, mock_Popen):
        skopeo = Mock()
        mock_Popen.return_value = skopeo
        self.proxy.update_cache()
        mock_Popen.assert_called_once_with(
            [
                'skopeo', 'copy',
                '--src-tls-verify=true',
                'docker://server/container:latest',
                'oci-archive:/dev/null:latest'
            ], stdout=-1, stderr=-1
        )
        skopeo.communicate.assert_called_once_with()
