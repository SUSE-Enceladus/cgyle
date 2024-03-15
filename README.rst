cgyle
=====

Simple cache update utility for proxy container registries.

cgyle aims to be useful for the `distribution` registry configured
as proxy (pull through cache) as it is documented here:

* https://distribution.github.io/distribution/recipes/mirror/

Such a registry caches the containers on demand. To allow a
pre-setup of the cache with a number of containers before a
user actually pulls it, cgyle can be used.

Such a pre-setup of the containers can be useful for low
bandwidth networks or disconnected server landscape.

Quickstart
==========

For a quick test of cgyle use the OCI container as follows

.. code:: bash

    podman pull pull registry.opensuse.org/home/marcus.schaefer/containers_tw/cgyle:latest
    podman run --rm -t cgyle cgyle --updatecache PROXY_URL --from https://registry.opensuse.org --filter '^opensuse/leap.*images.*toolbox' --dry-run

PROXY_URL points to a container registry of the above mentioned
configuration. It is expected that the container registry proxy
setup points to the same registry as used in the `--from` parameter
to lookup the container catalog.

To effectively trigger the cache update in the PROXY_URL, remove
the `--dry-run` option.

Run From Source
===============

To run from source the following steps are needed:

.. code:: bash

    ==> Clone this git

    cd cgyle
    poetry install
    poetry run cgyle --help
