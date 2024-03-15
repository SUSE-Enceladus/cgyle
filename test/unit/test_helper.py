import sys

# default commandline used for any test, overwrite when needed
sys.argv = [
    sys.argv[0], '--updatecache', 'localhost:5000', '--from', 'registry.opensuse.org'
]
argv_cgyle_tests = sys.argv
