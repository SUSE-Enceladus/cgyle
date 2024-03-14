from cgyle.cli import Cli

from .test_helper import argv_cgyle_tests


class TestCli:
    def setup(self):
        self.argv = argv_cgyle_tests
        self.cli = Cli()

    def setup_method(self, cls):
        self.setup()

    def test_Cli(self):
        Cli()
