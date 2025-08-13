buildroot = /

python_version = 3
python_lookup_name = python$(python_version)
python = $(shell which $(python_lookup_name))

version := $(shell \
	$(python) -c \
	'from cgyle.version import __version__; print(__version__)'\
)

setup:
	poetry install --all-extras

check: setup
	# shell code checks
	bash -c 'shellcheck tools/suse2ecr -s bash'
	# python flake tests
	poetry run flake8 --statistics -j auto --count cgyle
	poetry run flake8 --statistics -j auto --count test/unit

test: setup
	poetry run mypy cgyle
	poetry run bash -c 'pushd test/unit && pytest -n 5 \
		--doctest-modules --no-cov-on-fail --cov=cgyle \
		--cov-report=term-missing --cov-fail-under=100 \
		--cov-config .coveragerc'

git_attributes:
	# the following is required to update the $Format:%H$ git attribute
	# for details on when this target is called see setup.py
	git archive HEAD cgyle/version.py | tar -x

clean_git_attributes:
	# cleanup version.py to origin state
	# for details on when this target is called see setup.py
	git checkout cgyle/version.py

clean:
	rm -rf dist

build: clean check test
	# build the sdist source tarball
	poetry build --format=sdist
	# provide rpm source tarball
	mv dist/cgyle-${version}.tar.gz dist/python-cgyle.tar.gz
	# update rpm changelog using reference file
	helper/update_changelog.py --since package/python-cgyle.changes > \
		dist/python-cgyle.changes
	helper/update_changelog.py --file package/python-cgyle.changes >> \
		dist/python-cgyle.changes
	# update package version in spec file
	cat package/python-cgyle-spec-template | sed -e s'@%%VERSION@${version}@' \
		> dist/python-cgyle.spec
	# provide rpm rpmlintrc
	cp package/python-cgyle-rpmlintrc dist
