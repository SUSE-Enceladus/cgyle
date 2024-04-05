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
    @patch('shutil.rmtree')
    def test_update_cache_raises(self, mock_rmtree, mock_Popen):
        mock_Popen.side_effect = Exception
        with raises(CgyleCommandError):
            self.proxy.update_cache()

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('shutil.rmtree')
    def test_update_cache(self, mock_rmtree, mock_Popen):
        skopeo = Mock()
        skopeo.communicate.return_value = ('output', 'error')
        mock_Popen.return_value = skopeo
        self.proxy.update_cache(store_oci='some_dir')
        mock_Popen.assert_called_once_with(
            [
                'skopeo', 'sync', '--all', '--scoped',
                '--src-tls-verify=true', '--src', 'docker', '--dest', 'dir',
                'server/container', 'some_dir/container'
            ], stdout=-1, stderr=-1
        )
        skopeo.communicate.assert_called_once_with()

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('shutil.rmtree')
    @patch('os.path.exists')
    def test_update_cache_null_output(
        self, mock_os_path_exists, mock_rmtree, mock_Popen
    ):
        mock_os_path_exists.return_value = True
        skopeo = Mock()
        skopeo.communicate.return_value = ('output', 'error')
        mock_Popen.return_value = skopeo
        self.proxy.update_cache()
        mock_Popen.assert_called_once_with(
            [
                'skopeo', 'sync', '--all', '--scoped',
                '--src-tls-verify=true', '--src', 'docker', '--dest', 'dir',
                'server/container', '/var/tmp/to_delete'
            ], stdout=-1, stderr=-1
        )
        skopeo.communicate.assert_called_once_with()

    def test_get_pid(self):
        assert self.proxy.get_pid() == '0'

    @patch('cgyle.proxy.Catalog')
    @patch('cgyle.proxy.subprocess.Popen')
    @patch('cgyle.proxy.Path')
    def test_create_local_distribution_instance_raises(
        self, mock_Path, mock_Popen, mock_Catalog
    ):
        podman_create = Mock()
        podman_create.communicate.return_value = (b'output', b'error')
        mock_Popen.return_value = podman_create
        with patch('builtins.open', create=True):
            with raises(CgyleCommandError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote', 5000, 'bogus_creds'
                )
        with patch('builtins.open', create=True):
            with raises(CgyleCommandError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote'
                )
        podman_create.communicate.return_value = (b'output', b'')
        mock_Popen.side_effect = Exception
        with patch('builtins.open', create=True):
            with raises(CgyleCommandError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote'
                )

    @patch('time.sleep')
    @patch('cgyle.proxy.Catalog')
    @patch('cgyle.proxy.subprocess.Popen')
    @patch('cgyle.proxy.Path')
    def test_create_local_distribution_instance_connection_error(
        self, mock_Path, mock_Popen, mock_Catalog, mock_time
    ):
        podman_create = Mock()
        podman_create.communicate.return_value = (b'output', b'')
        mock_Popen.return_value = podman_create
        catalog = Mock()
        catalog.get_catalog.side_effect = Exception
        mock_Catalog.return_value = catalog
        with patch('builtins.open', create=True):
            with raises(CgyleCommandError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote'
                )

    @patch('os.path.abspath')
    @patch('cgyle.proxy.NamedTemporaryFile')
    @patch('cgyle.proxy.Catalog')
    @patch('cgyle.proxy.subprocess.Popen')
    @patch('cgyle.proxy.Path')
    def test_create_local_distribution_instance(
        self, mock_Path, mock_Popen, mock_Catalog, mock_NamedTemporaryFile,
        mock_os_path_abspath
    ):
        mock_os_path_abspath.return_value = 'some_abs_path'
        tmp_file = Mock()
        tmp_file.name = '/tmp/cgyle_local_distXXXX'
        mock_NamedTemporaryFile.return_value = tmp_file
        podman_create = Mock()
        podman_create.communicate.return_value = (b'output', b'')
        mock_Popen.return_value = podman_create
        with patch('builtins.open', create=True):
            self.proxy.create_local_distribution_instance(
                'data_dir', 'remote', 5000, 'user:pass'
            )
            mock_Path.assert_called_once_with('data_dir')
            mock_Popen.assert_called_once_with(
                [
                    'podman', 'run', '--detach',
                    '--name', 'cgyle_local_distXXXX',
                    '--net', 'host',
                    '-v', 'some_abs_path/:/var/lib/registry/',
                    '-v', '/tmp/cgyle_local_distXXXX:/etc/docker/registry/config.yml',
                    '-v', '/etc/pki/:/etc/pki/',
                    '-v', '/etc/hosts:/etc/hosts',
                    '-v', '/etc/ssl/:/etc/ssl/',
                    '-v', '/var/lib/ca-certificates/:/var/lib/ca-certificates/',
                    'docker.io/library/registry:latest'
                ], stdout=-1, stderr=-1
            )

    @patch('os.kill')
    def test_context_manager_exit_keyboard_interrupt(self, mock_os_kill):
        with raises(KeyboardInterrupt):
            with DistributionProxy('server', 'container') as proxy:
                proxy.pid = 1234
                raise KeyboardInterrupt
            mock_os_kill.assert_called_once_with()

    @patch('cgyle.proxy.subprocess.Popen')
    def test_context_manager_exit_registry_cleanup(self, mock_Popen):
        with DistributionProxy('server', 'container') as proxy:
            proxy.registry_name = 'some'
        mock_Popen.assert_called_once_with(
            ['podman', 'rm', '--force', 'some'], stdout=-1, stderr=-1
        )
