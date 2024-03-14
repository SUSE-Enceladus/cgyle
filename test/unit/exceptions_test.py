from unittest.mock import Mock
from cgyle.exceptions import CgyleError


class TestExceptions:
    def setup(self):
        self.error = Mock()

    def setup_method(self, cls):
        self.setup()

    def test_CgyleError(self):
        self.error.exception = CgyleError('message')
        assert format(self.error.exception) == 'message'
