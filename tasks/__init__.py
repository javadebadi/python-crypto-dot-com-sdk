from invoke.collection import Collection

from .code import ns_code
from .version import ns_version

ns = Collection()
ns.add_collection(ns_code)
ns.add_collection(ns_version)
