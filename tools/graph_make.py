import objgraph
import inspect
import sys
import os

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]), os.pardir, os.pardir))
sys.path.insert(0, possible_topdir)

from devstack import settings
from devstack.progs import common


distro = settings.RHEL6
comps = common.get_default_components()


def filter_c(c):
    if not inspect.isclass(c):
        return False
    if c is object:
        return False
    return True


actions = settings.ACTIONS
for action in actions:
    klss = list()

    for c in comps.keys():
        kls = common.get_action_cls(action, c, distro)
        klss.append(kls)
    
    max_depth = 5
    fn = "%s.png" % (action)
    objgraph.show_refs(klss,
                    filename=fn,
                    max_depth=max_depth,
                    highlight=inspect.isclass,
                    filter=filter_c,
                    extra_ignore=[id(locals())])
