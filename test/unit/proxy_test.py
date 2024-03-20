from unittest.mock import (
    patch, Mock
)
from pytest import (
    raises, fixture
)
from cgyle.proxy import DistributionProxy
from cgyle.exceptions import CgyleCommandError


class TestDistributionProxy:
    @fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def setup(self):
        self.proxy = DistributionProxy('https://server', 'container')

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
        skopeo.communicate.return_value = ('output', 'error')
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

    def test_get_pid(self):
        assert self.proxy.get_pid() == '0'

    @patch('os.kill')
    def test_context_manager_exit_keyboard_interrupt(self, mock_os_kill):
        with raises(KeyboardInterrupt):
            with DistributionProxy('server', 'container') as proxy:
                proxy.pid = 1234
                raise KeyboardInterrupt
            mock_os_kill.assert_called_once_with()
