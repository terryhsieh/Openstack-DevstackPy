# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import re

# These also have meaning outside python,
# ie in the pkg/pip listings so update there also!
UBUNTU11 = "ubuntu-oneiric"
RHEL6 = "rhel-6"
FEDORA16 = "fedora-16"

# What this program is called
PROG_NICE_NAME = "DEVSTACKpy"

# These 2 identify the json post and pre install sections
PRE_INSTALL = 'pre-install'
POST_INSTALL = 'post-install'

# Ip version constants for network ip detection
IPV4 = 'IPv4'
IPV6 = 'IPv6'

#how long to wait for a service to startup
WAIT_ALIVE_SECS = 5

# Component name mappings
NOVA = "nova"
NOVA_CLIENT = 'nova-client'
GLANCE = "glance"
QUANTUM = "quantum-server"
QUANTUM_CLIENT = 'quantum-client'
SWIFT = "swift"
HORIZON = "horizon"
KEYSTONE = "keystone"
KEYSTONE_CLIENT = 'keystone-client'
DB = "db"
RABBIT = "rabbit"
NOVNC = 'novnc'
XVNC = 'xvnc'
MELANGE = 'melange'
MELANGE_CLIENT = 'melange-client'
COMPONENT_NAMES = [
    NOVA, NOVA_CLIENT,
    GLANCE,
    QUANTUM, QUANTUM_CLIENT,
    SWIFT,
    HORIZON,
    KEYSTONE, KEYSTONE_CLIENT,
    DB,
    RABBIT,
    NOVNC,
    MELANGE, MELANGE_CLIENT,
]

# When a component is asked for it may
# need another component, that dependency
# mapping is listed here. A topological sort
# will be applied to determine the exact order.
COMPONENT_DEPENDENCIES = {
    DB: [],
    KEYSTONE_CLIENT: [],
    RABBIT: [],
    GLANCE: [KEYSTONE, DB],
    KEYSTONE: [DB, KEYSTONE_CLIENT],
    NOVA: [KEYSTONE, GLANCE, DB, RABBIT, NOVA_CLIENT],
    SWIFT: [KEYSTONE_CLIENT],
    NOVA_CLIENT: [],
    # Horizon depends on glances client (which should really be a client package)
    HORIZON: [KEYSTONE_CLIENT, GLANCE, NOVA_CLIENT, QUANTUM_CLIENT],
    # More of quantums deps come from its module function get_dependencies
    QUANTUM: [],
    NOVNC: [NOVA],
    QUANTUM_CLIENT: [],
    MELANGE: [DB],
    MELANGE_CLIENT: [],
}

# Different run types supported
RUN_TYPE_FORK = "FORK"
RUN_TYPE_UPSTART = "UPSTART"
RUN_TYPE_SCREEN = "SCREEN"
RUN_TYPE_DEF = RUN_TYPE_FORK
RUN_TYPES_KNOWN = [RUN_TYPE_UPSTART,
                    RUN_TYPE_FORK,
                    RUN_TYPE_SCREEN,
                    RUN_TYPE_DEF]

# Used to find the type in trace files
RUN_TYPE_TYPE = "TYPE"

# Default subdirs of a components root directory
COMPONENT_TRACE_DIR = "traces"
COMPONENT_APP_DIR = "app"
COMPONENT_CONFIG_DIR = "config"

# RC files generated / used
RC_FN_TEMPL = "os-%s.rc"
EC2RC_FN = RC_FN_TEMPL % ('ec2')
LOCALRC_FN = RC_FN_TEMPL % ('local')
OSRC_FN = RC_FN_TEMPL % ('core')

# Program
# actions
INSTALL = "install"
UNINSTALL = "uninstall"
START = "start"
STOP = "stop"
ACTIONS = [INSTALL, UNINSTALL, START, STOP]

# Where the configs and templates should be at.
STACK_CONFIG_DIR = os.path.join(os.getcwd(), "conf")
STACK_TEMPLATE_DIR = os.path.join(STACK_CONFIG_DIR, "templates")
STACK_PKG_DIR = os.path.join(STACK_CONFIG_DIR, "pkgs")
STACK_PIP_DIR = os.path.join(STACK_CONFIG_DIR, "pips")
STACK_CONFIG_LOCATION = os.path.join(STACK_CONFIG_DIR, "stack.ini")
STACK_LOG_CFG_LOCATION = os.path.join(STACK_CONFIG_DIR, "logging.ini")
STACK_LOG_ENV_LOCATION = 'LOG_FILE'

# These regex is how we match python platform output to a known constant
KNOWN_DISTROS = {
    UBUNTU11: re.compile(r'Ubuntu(.*)oneiric', re.IGNORECASE),
    RHEL6: re.compile(r'redhat-6\.2', re.IGNORECASE),
    FEDORA16: re.compile(r'fedora-16', re.IGNORECASE),
}
