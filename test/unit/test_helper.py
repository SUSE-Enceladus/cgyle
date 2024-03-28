import sys

# default commandline used for any test, overwrite when needed
sys.argv = [
    sys.argv[0], '--updatecache', 'local://distribution:some', '--from', 'registry.opensuse.org'
]
argv_cgyle_tests = sys.argv
