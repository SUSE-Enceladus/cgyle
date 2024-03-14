buildroot = /

python_version = 3
python_lookup_name = python$(python_version)
python = $(shell which $(python_lookup_name))

version := $(shell \
	$(python) -c \
	'from cgyle.version import __version__; print(__version__)'\
)

tox:
	tox -- "-n 5"

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

build: clean tox
	# build the sdist source tarball
	poetry build --format=sdist
	# provide rpm source tarball
	mv dist/cgyle-${version}.tar.gz dist/python-cgyle.tar.gz
	# update package version in spec file
	cat package/python-cgyle-spec-template | sed -e s'@%%VERSION@${version}@' \
		> dist/python-cgyle.spec
	# provide rpm rpmlintrc
	cp package/python-cgyle-rpmlintrc dist
