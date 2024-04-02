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

To run from source the following steps are needed:

.. code:: bash

    ==> Clone this git

    cd cgyle
    poetry install

    poetry run cgyle --help

1. Trigger a cache update in an already running proxy

    .. code:: bash

        poetry run cgyle --updatecache PROXY_URL --from https://registry.opensuse.org --filter '^opensuse/leap.*images.*toolbox'

   PROXY_URL points to a container registry of the above mentioned
   configuration. It is expected that the container registry proxy
   setup points to the same registry as used in the `--from` parameter
   to lookup the container catalog.

   To effectively trigger the cache update in the PROXY_URL, add
   the `--apply` option.

2. Create a local **distribution format** data tree mirror

    .. code:: bash

        poetry run cgyle --updatecache local://distribution:my_mirror --from https://registry.opensuse.org --filter '^opensuse/leap.*images.*toolbox' --apply

   Find the data tree below the `my_mirror` directory
