import io
from unittest.mock import (
    patch, Mock, MagicMock, call
)
from pytest import (
    raises, fixture
)
from cgyle.proxy import DistributionProxy
from subprocess import SubprocessError
from cgyle.exceptions import (
    CgyleCommandError, CgyleCredentialsError
)
from json import JSONDecodeError


class TestDistributionProxy:
    @fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def setup(self):
        self.proxy = DistributionProxy('https://server', 'container')

    def setup_method(self, cls):
        self.setup()

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('os.unlink')
    @patch('cgyle.proxy.Path')
    @patch('cgyle.proxy.DistributionProxy')
    def test_update_cache_raises(
        self, mock_DistributionProxy, mock_Path, mock_os_unlink, mock_Popen
    ):
        proxy = Mock()
        proxy.get_tags.return_value = ['latest']
        mock_DistributionProxy.return_value = proxy
        mock_Popen.side_effect = SubprocessError
        with raises(CgyleCommandError):
            self.proxy.update_cache(from_registry='some_registry')
        with raises(CgyleCredentialsError):
            self.proxy.update_cache(
                from_registry='some_registry', store_oci='some_dir',
                proxy_creds='bogus_creds'
            )

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('os.unlink')
    @patch('cgyle.proxy.Path')
    @patch('cgyle.proxy.DistributionProxy')
    @patch('os.path.exists')
    def test_update_cache(
        self, mock_os_path_exists,
        mock_DistributionProxy, mock_Path, mock_os_unlink, mock_Popen
    ):
        mock_os_path_exists.return_value = True
        proxy = Mock()
        proxy.get_tags.return_value = ['latest']
        mock_DistributionProxy.return_value = proxy
        skopeo = Mock()
        skopeo.returncode = 0
        skopeo.communicate.return_value = ('stdout', 'stderr')
        mock_Popen.return_value = skopeo
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = MagicMock(spec=io.IOBase)
            file_handle = mock_open.return_value.__enter__.return_value
            file_handle.readline.return_value = ['tagname']
            self.proxy.update_cache(
                from_registry='some_registry', store_oci='some_dir',
                proxy_creds='user:pass'
            )
            mock_Popen.assert_called_once_with(
                [
                    'skopeo', 'copy', '--all',
                    '--dest-oci-accept-uncompressed-layers',
                    '--retry-times', '5',
                    '--image-parallel-copies', '5',
                    '--src-tls-verify=true',
                    '--src-creds', 'user:pass',
                    'docker://server/container:latest',
                    'oci-archive:some_dir/container-latest-all.oci.tar:latest'
                ], stdout=file_handle, stderr=file_handle
            )
            assert skopeo.communicate.called

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('os.unlink')
    @patch('cgyle.proxy.Path')
    @patch('cgyle.proxy.DistributionProxy')
    def test_update_cache_multi_arch(
        self, mock_DistributionProxy, mock_Path, mock_os_unlink, mock_Popen
    ):
        proxy = Mock()
        proxy.get_tags.return_value = ['latest']
        mock_DistributionProxy.return_value = proxy
        skopeo = Mock()
        skopeo.returncode = 0
        skopeo.communicate.return_value = ('stdout', 'stderr')
        mock_Popen.return_value = skopeo
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = MagicMock(spec=io.IOBase)
            file_handle = mock_open.return_value.__enter__.return_value
            self.proxy.update_cache(
                from_registry='some_registry',
                store_oci='some_dir',
                proxy_creds='user:pass',
                use_archs=['x86_64']
            )
            mock_Popen.assert_called_once_with(
                [
                    'skopeo', '--override-arch', 'x86_64',
                    'copy', '--dest-oci-accept-uncompressed-layers',
                    '--retry-times', '5',
                    '--image-parallel-copies', '5',
                    '--src-tls-verify=true',
                    '--src-creds', 'user:pass',
                    'docker://server/container:latest',
                    'oci-archive:some_dir/container-latest-x86_64.oci.tar:latest'
                ], stdout=file_handle, stderr=file_handle
            )
            assert skopeo.communicate.called

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('os.unlink')
    @patch('cgyle.proxy.Path')
    @patch('cgyle.proxy.DistributionProxy')
    def test_update_cache_null_output(
        self, mock_DistributionProxy, mock_Path, mock_os_unlink, mock_Popen
    ):
        proxy = Mock()
        proxy.get_tags.return_value = ['latest']
        mock_DistributionProxy.return_value = proxy
        skopeo = Mock()
        skopeo.returncode = 1
        mock_Popen.return_value = skopeo
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = MagicMock(spec=io.IOBase)
            file_handle = mock_open.return_value.__enter__.return_value
            self.proxy.update_cache(from_registry='some_registry')
            mock_Popen.assert_called_once_with(
                [
                    'skopeo', 'copy', '--all',
                    '--dest-oci-accept-uncompressed-layers',
                    '--retry-times', '5',
                    '--image-parallel-copies', '5',
                    '--src-tls-verify=true',
                    'docker://server/container:latest',
                    'oci-archive:/dev/null:latest'
                ], stdout=file_handle, stderr=file_handle
            )
            skopeo.communicate.assert_called_once_with()

    def test_get_pid(self):
        assert self.proxy.get_pid() == '0'

    @patch('cgyle.proxy.Catalog')
    @patch('cgyle.proxy.subprocess.Popen')
    @patch('cgyle.proxy.Path')
    @patch('cgyle.proxy.NamedTemporaryFile')
    def test_create_local_distribution_instance_raises(
        self, mock_NamedTemporaryFile, mock_Path, mock_Popen, mock_Catalog
    ):
        popen_results = [
            Mock(
                returncode=1,
                communicate=Mock(return_value=(b'output', b'error'))
            ),
            Mock(
                returncode=0,
                communicate=Mock(return_value=(b'output', b''))
            )
        ]

        def podman(*args, **kwargs):
            return popen_results.pop()

        podman_call = Mock()
        podman_call.communicate.return_value = (b'output', b'error')
        podman_call.returncode = 1
        mock_Popen.return_value = podman_call
        with patch('builtins.open', create=True):
            with raises(CgyleCredentialsError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote', 5000, 'bogus_creds'
                )
        with patch('builtins.open', create=True):
            with raises(CgyleCommandError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote'
                )
        podman_call.communicate.return_value = (b'output', b'')
        mock_Popen.side_effect = SubprocessError
        with patch('builtins.open', create=True):
            with raises(CgyleCommandError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote'
                )
        mock_Popen.reset_mock()
        mock_Popen.side_effect = podman
        with patch('builtins.open', create=True):
            with raises(CgyleCommandError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote'
                )

    @patch('time.sleep')
    @patch('cgyle.proxy.Catalog')
    @patch('cgyle.proxy.subprocess.Popen')
    @patch('cgyle.proxy.Path')
    @patch('cgyle.proxy.NamedTemporaryFile')
    def test_create_local_distribution_instance_connection_error(
        self, mock_NamedTemporaryFile, mock_Path, mock_Popen,
        mock_Catalog, mock_time
    ):
        podman_call = Mock()
        podman_call.returncode = 0
        podman_call.communicate.return_value = (b'output', b'')
        mock_Popen.return_value = podman_call
        catalog = Mock()
        catalog.get_catalog.side_effect = Exception
        mock_Catalog.return_value = catalog
        with patch('builtins.open', create=True):
            with raises(CgyleCommandError):
                self.proxy.create_local_distribution_instance(
                    'data_dir', 'remote'
                )

    @patch('os.unlink')
    @patch('json.load')
    @patch('os.path.exists')
    @patch('os.path.abspath')
    @patch('cgyle.proxy.NamedTemporaryFile')
    @patch('cgyle.proxy.Catalog')
    @patch('cgyle.proxy.subprocess.Popen')
    @patch('cgyle.proxy.Path')
    def test_create_local_distribution_instance_state_file_error(
        self, mock_Path, mock_Popen, mock_Catalog, mock_NamedTemporaryFile,
        mock_os_path_abspath, mock_os_path_exists, mock_json_load,
        mock_os_unlink
    ):
        mock_os_path_abspath.return_value = 'some_abs_path'
        tmp_file = Mock()
        tmp_file.name = '/tmp/cgyle_local_distXXXX'
        mock_NamedTemporaryFile.return_value = tmp_file
        podman_call = Mock()
        podman_call.returncode = 0
        podman_call.communicate.return_value = (b'output', b'')
        mock_Popen.return_value = podman_call
        mock_os_path_exists.return_value = True
        mock_json_load.side_effect = JSONDecodeError('msg', 'doc', 1)
        with patch('builtins.open', create=True):
            self.proxy.create_local_distribution_instance(
                'data_dir', 'remote', 5000, 'user:pass'
            )
        mock_os_unlink.assert_called_once_with(
            'some_abs_path/scheduler-state.json'
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
        podman_call = Mock()
        podman_call.returncode = 0
        podman_call.communicate.return_value = (b'output', b'')
        mock_Popen.return_value = podman_call
        with patch('builtins.open', create=True):
            self.proxy.create_local_distribution_instance(
                'data_dir', 'remote', 5000, 'user:pass'
            )
            mock_Path.assert_called_once_with('data_dir')
            assert mock_Popen.call_args_list == [
                call(
                    ['podman', 'image', 'exists', 'registry'], stdout=-1, stderr=-1
                ),
                call(
                    [
                        'podman', 'run', '--detach',
                        '--name', 'cgyle_local_distXXXX',
                        '--rm',
                        '--net', 'host',
                        '-v', 'some_abs_path/:/var/lib/registry/',
                        '-v', '/tmp/cgyle_local_distXXXX:/etc/docker/registry/config.yml',
                        '-v', '/var/log/cgyle_proxy.log:/var/log/cgyle_proxy.log',
                        '-v', '/etc/pki/:/etc/pki/',
                        '-v', '/etc/hosts:/etc/hosts',
                        '-v', '/etc/ssl/:/etc/ssl/',
                        '-v', '/var/lib/ca-certificates/:/var/lib/ca-certificates/',
                        'registry:latest',
                        'sh', '-c', 'registry serve /etc/docker/registry/config.yml &>/var/log/cgyle_proxy.log'
                    ], stdout=-1, stderr=-1
                )
            ]

    @patch('cgyle.proxy.subprocess.Popen')
    def test_get_tags_no_logfile(self, mock_Popen):
        skopeo = Mock()
        skopeo.returncode = 0
        skopeo.communicate.return_value = ['{"RepoTags": ["name"],"Architecture": "amd64"}', '']
        mock_Popen.return_value = skopeo
        assert self.proxy.get_tags(True, 'user:pass') == ['name']
        assert self.proxy.get_tags(True, 'user:pass', 'amd64') == ['name']
        assert self.proxy.get_tags(True, 'user:pass', 's390x') == []
        skopeo.returncode = 1
        with raises(CgyleCommandError):
            self.proxy.get_tags()
        mock_Popen.side_effect = SubprocessError
        with raises(CgyleCommandError):
            self.proxy.get_tags()

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('os.unlink')
    def test_get_tags_with_logfile(self, mock_os_unlink, mock_Popen):
        skopeo = Mock()
        skopeo.returncode = 0
        skopeo.communicate.return_value = ['{"RepoTags": ["name"],"Architecture": "amd64"}', '']
        mock_Popen.return_value = skopeo
        with patch('builtins.open', create=True):
            self.proxy.get_tags(True, 'user:pass', 'amd64', 'some-log-file')

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('os.unlink')
    def test_get_tags_podman_search(self, mock_os_unlink, mock_Popen):
        first = Mock()
        first.returncode = 1
        first.communicate.return_value = ['', '']
        second = Mock()
        second.returncode = 0
        second.communicate.return_value = [b'tag1\ntag2', b'']
        skopeos = [
            second, first
        ]

        def calls(argc, **argv):
            return skopeos.pop()

        mock_Popen.side_effect = calls
        with patch('builtins.open', create=True):
            assert self.proxy.get_tags(
                True, 'user:pass', 'amd64', 'some-log-file'
            ) == ['tag1', 'tag2']

    @patch('cgyle.proxy.subprocess.Popen')
    @patch('os.unlink')
    def test_get_tags_podman_search_on_invalid_container_arch(
        self, mock_os_unlink, mock_Popen
    ):
        first = Mock()
        first.returncode = 1
        first.communicate.return_value = ['', '']
        second = Mock()
        second.returncode = 0
        second.communicate.return_value = [b'tag1\ntag2', b'']
        skopeos = [
            second, first
        ]

        def calls(argc, **argv):
            return skopeos.pop()

        mock_Popen.side_effect = calls
        with patch('builtins.open', create=True):
            assert self.proxy.get_tags(
                True, 'user:pass', 'x86_64', 'some-log-file'
            ) == []

    @patch('os.kill')
    @patch('psutil.pid_exists')
    @patch('cgyle.proxy.Path')
    @patch('cgyle.proxy.DistributionProxy')
    def test_context_manager_exit_keyboard_interrupt(
        self, mock_DistributionProxy, mock_Path, mock_pid_exists, mock_os_kill
    ):
        mock_pid_exists.return_value = True
        proxy = Mock()
        proxy.get_tags.return_value = ['latest']
        mock_DistributionProxy.return_value = proxy
        with raises(KeyboardInterrupt):
            with DistributionProxy('server', 'container') as proxy:
                proxy.pid = 1234
                proxy.shutdown = True
                proxy.update_cache(from_registry='some_registry')
                raise KeyboardInterrupt
            mock_os_kill.assert_called_once_with()

    @patch('cgyle.proxy.subprocess.Popen')
    def test_context_manager_exit_registry_cleanup(self, mock_Popen):
        with DistributionProxy('server', 'container') as proxy:
            proxy.registry_name = 'some'
        mock_Popen.assert_called_once_with(
            ['podman', 'rm', '--force', 'some'], stdout=-1, stderr=-1
        )
