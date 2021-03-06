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

from urlparse import urlunparse

import io
import os
import time

from devstack import cfg
from devstack import component as comp
from devstack import date
from devstack import exceptions
from devstack import libvirt as virsh
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.components import db
from devstack.components import keystone


#id
TYPE = settings.NOVA
LOG = logging.getLogger('devstack.components.nova')

#special generated conf
API_CONF = 'nova.conf'

#normal conf
PASTE_CONF = 'nova-api-paste.ini'
PASTE_SOURCE_FN = 'api-paste.ini'
POLICY_CONF = 'policy.json'
LOGGING_SOURCE_FN = 'logging_sample.conf'
LOGGING_CONF = "logging.conf"
CONFIGS = [PASTE_CONF, POLICY_CONF, LOGGING_CONF]
ADJUST_CONFIGS = [PASTE_CONF]

#this is a special conf
NET_INIT_CONF = 'nova-network-init.sh'
NET_INIT_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]

#this db will be dropped then created
DB_NAME = 'nova'

#this makes the database be in sync with nova
DB_SYNC_CMD = [
    {'cmd': ['%BINDIR%/nova-manage', '--flagfile', '%CFGFILE%',
             'db', 'sync']},
]

#these are used for nova volumens
VG_CHECK_CMD = [
    {'cmd': ['vgs', '%VOLUME_GROUP%'],
     'run_as_root': True}
]
VG_DEV_CMD = [
    {'cmd': ['losetup', '-f', '--show', '%VOLUME_BACKING_FILE%'],
     'run_as_root': True}
]
VG_CREATE_CMD = [
    {'cmd': ['vgcreate', '%VOLUME_GROUP%', '%DEV%'],
     'run_as_root': True}
]
VG_LVS_CMD = [
    {'cmd': ['lvs', '--noheadings', '-o', 'lv_name', '%VOLUME_GROUP%'],
     'run_as_root': True}
]
VG_LVREMOVE_CMD = [
    {'cmd': ['lvremove', '-f', '%VOLUME_GROUP%/%LV%'],
     'run_as_root': True}
]
RESTART_TGT_CMD = [
    {'cmd': ['stop', 'tgt'], 'run_as_root': True},
    {'cmd': ['start', 'tgt'], 'run_as_root': True}
]

# NCPU, NVOL, NAPI ... are here as possible subcomponents of nova
NCPU = "cpu"
NVOL = "vol"
NAPI = "api"
NOBJ = "obj"
NNET = "net"
NCERT = "cert"
NSCHED = "sched"
NCAUTH = "cauth"
NXVNC = "xvnc"
SUBCOMPONENTS = [NCPU, NVOL, NAPI,
    NOBJ, NNET, NCERT, NSCHED, NCAUTH, NXVNC]

#the pkg json files nova requires for installation
REQ_PKGS = ['general.json', 'nova.json']

# Additional packages for subcomponents
ADD_PKGS = {
    NAPI:
        [
            'n-api.json',
        ],
    NCPU:
        [
            'n-cpu.json',
        ],
    NVOL:
        [
            'n-vol.json',
        ],
}

# Adjustments to nova paste pipeline for keystone
PASTE_PIPELINE_KEYSTONE_ADJUST = {
    'pipeline:ec2cloud': {'pipeline': 'ec2faultwrap logrequest totoken authtoken keystonecontext cloudrequest authorizer ec2executor'},
    'pipeline:ec2admin': {'pipeline': "ec2faultwrap logrequest totoken authtoken keystonecontext adminrequest authorizer ec2executor"},
    'pipeline:openstack_compute_api_v2': {'pipeline': "faultwrap authtoken keystonecontext ratelimit osapi_compute_app_v2"},
    'pipeline:openstack_volume_api_v1': {'pipeline': "faultwrap authtoken keystonecontext ratelimit osapi_volume_app_v1"},
    'pipeline:openstack_api_v2': {'pipeline': 'faultwrap authtoken keystonecontext ratelimit osapi_app_v2'},
}

# What to start
APP_OPTIONS = {
    #these are currently the core components/applications
    'nova-api': ['--flagfile', '%CFGFILE%'],
    'nova-compute': ['--flagfile', '%CFGFILE%'],
    'nova-volume': ['--flagfile', '%CFGFILE%'],
    'nova-network': ['--flagfile', '%CFGFILE%'],
    'nova-scheduler': ['--flagfile', '%CFGFILE%'],
    'nova-cert': ['--flagfile', '%CFGFILE%'],
    'nova-objectstore': ['--flagfile', '%CFGFILE%'],
    'nova-consoleauth': ['--flagfile', '%CFGFILE%'],
    'nova-xvpvncproxy': ['--flagfile', '%CFGFILE%'],
}

# Sub component names to actual app names (matching previous dict)
SUB_COMPONENT_NAME_MAP = {
    NCPU: 'nova-compute',
    NVOL: 'nova-volume',
    NAPI: 'nova-api',
    NOBJ: 'nova-objectstore',
    NNET: 'nova-network',
    NCERT: 'nova-cert',
    NSCHED: 'nova-scheduler',
    NCAUTH: 'nova-consoleauth',
    NXVNC: 'nova-xvpvncproxy',
}

#subdirs of the checkout/download
BIN_DIR = 'bin'
CONFIG_DIR = "etc"

#network class/driver/manager templs
QUANTUM_MANAGER = 'nova.network.quantum.manager.QuantumManager'
QUANTUM_IPAM_LIB = 'nova.network.quantum.melange_ipam_lib'
NET_MANAGER_TEMPLATE = 'nova.network.manager.%s'

#sensible defaults
DEF_IMAGE_SERVICE = 'nova.image.glance.GlanceImageService'
DEF_SCHEDULER = 'nova.scheduler.simple.SimpleScheduler'
DEF_GLANCE_PORT = 9292
DEF_GLANCE_SERVER = "%s" + ":%s" % (DEF_GLANCE_PORT)
DEF_INSTANCE_PREFIX = 'instance-'
DEF_INSTANCE_TEMPL = DEF_INSTANCE_PREFIX + '%08x'
DEF_FIREWALL_DRIVER = 'nova.virt.firewall.IptablesFirewallDriver'
DEF_FLAT_VIRT_BRIDGE = 'br100'
DEF_NET_MANAGER = 'FlatDHCPManager'
DEF_VOL_PREFIX = 'volume-'
DEF_VOL_TEMPL = DEF_VOL_PREFIX + '%08x'

#default virt types
DEF_VIRT_DRIVER = virsh.VIRT_TYPE
DEF_VIRT_TYPE = 'qemu'

#virt drivers to there connection name
VIRT_DRIVER_CON_MAP = {
    virsh.VIRT_TYPE: 'libvirt',
    'xenserver': 'xenapi',
    'vmware': 'vmwareapi',
    'baremetal': 'baremetal',
}

#only turned on if vswitch enabled
QUANTUM_OPENSWITCH_OPS = {
    'libvirt_vif_type': 'ethernet',
    'libvirt_vif_driver': 'nova.virt.libvirt.vif.LibvirtOpenVswitchDriver',
    'linuxnet_interface_driver': 'nova.network.linux_net.LinuxOVSInterfaceDriver',
    'quantum_use_dhcp': None,
}

#this is a special conf
CLEANER_DATA_CONF = 'nova-clean.sh'
CLEANER_CMD_ROOT = [sh.joinpths("/", "bin", 'bash')]

#rhel6/fedora libvirt policy
#http://wiki.libvirt.org/page/SSHPolicyKitSetup
LIBVIRT_POLICY_FN = "/etc/polkit-1/localauthority/50-local.d/50-libvirt-remote-access.pkla"
LIBVIRT_POLICY_CONTENTS = """
[libvirt Management Access]
Identity=unix-group:libvirtd
Action=org.libvirt.unix.manage
ResultAny=yes
ResultInactive=yes
ResultActive=yes
"""
POLICY_DISTROS = [settings.RHEL6, settings.FEDORA16]

#xenserver specific defaults
XS_DEF_INTERFACE = 'eth1'
XA_CONNECTION_ADDR = '169.254.0.1'
XS_VNC_ADDR = XA_CONNECTION_ADDR
XS_DEF_BRIDGE = 'xapi1'
XA_CONNECTION_PORT = 80
XA_DEF_USER = 'root'
XA_DEF_CONNECTION_URL = urlunparse(('http', "%s:%s" % (XA_CONNECTION_ADDR, XA_CONNECTION_PORT), "", '', '', ''))

#vnc specific defaults
VNC_DEF_ADDR = '127.0.0.1'

#std compute extensions
STD_COMPUTE_EXTS = 'nova.api.openstack.compute.contrib.standard_extensions'

#pip files that nova requires
REQ_PIPS = ['general.json', 'nova.json']

#config keys we warm up so u won't be prompted later
WARMUP_PWS = ['rabbit']

#used to wait until started before we can run the data setup script
WAIT_ONLINE_TO = settings.WAIT_ALIVE_SECS


def _canon_virt_driver(virt_driver):
    if not virt_driver:
        return DEF_VIRT_DRIVER
    virt_driver = virt_driver.strip().lower()
    if not (virt_driver in VIRT_DRIVER_CON_MAP):
        return DEF_VIRT_DRIVER
    return virt_driver


def _canon_libvirt_type(virt_type):
    if not virt_type:
        return DEF_VIRT_TYPE
    virt_type = virt_type.lower().strip()
    if not (virt_type in virsh.LIBVIRT_PROTOCOL_MAP):
        return DEF_VIRT_TYPE
    else:
        return virt_type


class NovaUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)

    def pre_uninstall(self):
        self._clear_libvirt_domains()
        self._clean_it()

    def _clean_it(self):
        #these environment additions are important
        #in that they eventually affect how this script runs
        sub_components = self.component_opts or SUBCOMPONENTS
        env = dict()
        env['ENABLED_SERVICES'] = ",".join(sub_components)
        env['BIN_DIR'] = self.bindir
        env['VOLUME_NAME_PREFIX'] = self.cfg.getdefaulted('nova', 'volume_name_prefix', DEF_VOL_PREFIX)
        cleaner_fn = sh.joinpths(self.bindir, CLEANER_DATA_CONF)
        if sh.isfile(cleaner_fn):
            LOG.info("Cleaning up your system by running nova cleaner script [%s]." % (cleaner_fn))
            cmd = CLEANER_CMD_ROOT + [cleaner_fn]
            sh.execute(*cmd, run_as_root=True, env_overrides=env)

    def _clear_libvirt_domains(self):
        virt_driver = _canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if virt_driver == virsh.VIRT_TYPE:
            inst_prefix = self.cfg.getdefaulted('nova', 'instance_name_prefix', DEF_INSTANCE_PREFIX)
            libvirt_type = _canon_libvirt_type(self.cfg.get('nova', 'libvirt_type'))
            virsh.clear_libvirt_domains(self.distro, libvirt_type, inst_prefix)


class NovaInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.paste_conf_fn = self._get_target_config_name(PASTE_CONF)
        self.volumes_enabled = False
        if not self.component_opts or NVOL in self.component_opts:
            self.volumes_enabled = True
        self.xvnc_enabled = False
        if not self.component_opts or NXVNC in self.component_opts:
            self.xvnc_enabled = True

    def _get_pkgs(self):
        pkgs = list(REQ_PKGS)
        sub_components = self.component_opts or SUBCOMPONENTS
        for c in sub_components:
            fns = ADD_PKGS.get(c, [])
            pkgs.extend(fns)
        return pkgs

    def _get_symlinks(self):
        links = comp.PythonInstallComponent._get_symlinks(self)
        source_fn = sh.joinpths(self.cfgdir, API_CONF)
        links[source_fn] = sh.joinpths(self._get_link_dir(), API_CONF)
        return links

    def _get_pips(self):
        return list(REQ_PIPS)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "nova_repo"),
            'branch': ("git", "nova_branch"),
        })
        return places

    def warm_configs(self):
        for pw_key in WARMUP_PWS:
            self.cfg.get("passwords", pw_key)
        driver_canon = _canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if driver_canon == 'xenserver':
            self.cfg.get("passwords", "xenapi_connection")

    def _get_config_files(self):
        return list(CONFIGS)

    def _setup_network_initer(self):
        LOG.info("Configuring nova network initializer template %s.", NET_INIT_CONF)
        (_, contents) = utils.load_template(self.component_name, NET_INIT_CONF)
        params = self._get_param_map(NET_INIT_CONF)
        contents = utils.param_replace(contents, params, True)
        tgt_fn = sh.joinpths(self.bindir, NET_INIT_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 0755)
        self.tracewriter.file_touched(tgt_fn)

    def _sync_db(self):
        LOG.info("Syncing the database with nova.")
        mp = dict()
        mp['BINDIR'] = self.bindir
        mp['CFGFILE'] = sh.joinpths(self.cfgdir, API_CONF)
        utils.execute_template(*DB_SYNC_CMD, params=mp)

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        #extra actions to do nova setup
        self._setup_db()
        self._sync_db()
        self._setup_cleaner()
        self._setup_network_initer()
        #check if we need to do the vol subcomponent
        if self.volumes_enabled:
            vol_maker = NovaVolumeConfigurator(self)
            vol_maker.setup_volumes()

    def _setup_cleaner(self):
        LOG.info("Configuring cleaner template %s.", CLEANER_DATA_CONF)
        (_, contents) = utils.load_template(self.component_name, CLEANER_DATA_CONF)
        tgt_fn = sh.joinpths(self.bindir, CLEANER_DATA_CONF)
        sh.write_file(tgt_fn, contents)
        sh.chmod(tgt_fn, 0755)
        self.tracewriter.file_touched(tgt_fn)

    def _setup_db(self):
        LOG.info("Fixing up database named %s.", DB_NAME)
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _generate_nova_conf(self):
        LOG.info("Generating dynamic content for nova configuration (%s)." % (API_CONF))
        conf_gen = NovaConfConfigurator(self)
        nova_conf = conf_gen.configure()
        tgtfn = self._get_target_config_name(API_CONF)
        LOG.info("Writing nova configuration to %s" % (tgtfn))
        LOG.debug(nova_conf)
        self.tracewriter.make_dir(sh.dirname(tgtfn))
        sh.write_file(tgtfn, nova_conf)
        self.tracewriter.cfg_write(tgtfn)

    def _config_adjust(self, contents, config_fn):
        if config_fn not in ADJUST_CONFIGS:
            return contents
        if config_fn == PASTE_CONF and utils.service_enabled(settings.KEYSTONE, self.instances, False):
            newcontents = contents
            with io.BytesIO(contents) as stream:
                config = cfg.IgnoreMissingConfigParser()
                config.readfp(stream)
                mods = 0
                for section in PASTE_PIPELINE_KEYSTONE_ADJUST.keys():
                    if config.has_section(section):
                        section_vals = PASTE_PIPELINE_KEYSTONE_ADJUST.get(section)
                        for (k, v) in section_vals.items():
                            config.set(section, k, v)
                            mods += 1
                if mods > 0:
                    with io.BytesIO() as outputstream:
                        config.write(outputstream)
                        outputstream.flush()
                        newcontents = cfg.add_header(config_fn, outputstream.getvalue())
            contents = newcontents
        return contents

    def _get_source_config(self, config_fn):
        name = config_fn
        if config_fn == PASTE_CONF:
            name = PASTE_SOURCE_FN
        elif config_fn == LOGGING_CONF:
            name = LOGGING_SOURCE_FN
        srcfn = sh.joinpths(self.cfgdir, "nova", name)
        contents = sh.load_file(srcfn)
        return (srcfn, contents)

    def _get_param_map(self, config_fn):
        mp = dict()
        if config_fn == NET_INIT_CONF:
            mp['NOVA_DIR'] = self.appdir
            mp['CFG_FILE'] = sh.joinpths(self.cfgdir, API_CONF)
            mp['FLOATING_RANGE'] = self.cfg.get('nova', 'floating_range')
            mp['TEST_FLOATING_RANGE'] = self.cfg.get('nova', 'test_floating_range')
            mp['TEST_FLOATING_POOL'] = self.cfg.get('nova', 'test_floating_pool')
            mp['FIXED_NETWORK_SIZE'] = self.cfg.get('nova', 'fixed_network_size')
            mp['FIXED_RANGE'] = self.cfg.get('nova', 'fixed_range')
        else:
            mp = keystone.get_shared_params(self.cfg)
            mp['SERVICE_PASSWORD'] = "???"
            mp['SERVICE_USER'] = "???"
        return mp

    def configure(self):
        configs_made = comp.PythonInstallComponent.configure(self)
        self._generate_nova_conf()
        configs_made += 1
        # TODO: maybe this should be a subclass that handles these differences
        driver_canon = _canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if (self.distro in POLICY_DISTROS) and driver_canon == virsh.VIRT_TYPE:
            with sh.Rooted(True):
                dirsmade = sh.mkdirslist(sh.dirname(LIBVIRT_POLICY_FN))
                sh.write_file(LIBVIRT_POLICY_FN, LIBVIRT_POLICY_CONTENTS)
            self.tracewriter.dir_made(*dirsmade)
            self.tracewriter.cfg_write(LIBVIRT_POLICY_FN)
            configs_made += 1
        return configs_made


class NovaRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)
        self.bindir = sh.joinpths(self.appdir, BIN_DIR)

    def _setup_network_init(self):
        tgt_fn = sh.joinpths(self.bindir, NET_INIT_CONF)
        if sh.isfile(tgt_fn):
            LOG.info("Creating your nova network to be used with instances.")
            #still there, run it
            #these environment additions are important
            #in that they eventually affect how this script runs
            if utils.service_enabled(settings.QUANTUM, self.instances, False):
                LOG.info("Waiting %s seconds so that quantum can start up before running first time init." % (WAIT_ONLINE_TO))
                time.sleep(WAIT_ONLINE_TO)
            env = dict()
            env['ENABLED_SERVICES'] = ",".join(self.instances.keys())
            setup_cmd = NET_INIT_CMD_ROOT + [tgt_fn]
            LOG.info("Running (%s) command to initialize nova's network." % (" ".join(setup_cmd)))
            sh.execute(*setup_cmd, env_overrides=env, run_as_root=False)
            LOG.debug("Removing (%s) file since we successfully initialized nova's network." % (tgt_fn))
            sh.unlink(tgt_fn)

    def post_start(self):
        self._setup_network_init()

    def get_dependencies(self):
        deps = comp.PythonRuntime.get_dependencies(self)
        if utils.service_enabled(settings.QUANTUM, self.instances, False):
            deps.append(settings.QUANTUM)
        return deps

    def _get_apps_to_start(self):
        result = list()
        if not self.component_opts:
            apps = sorted(APP_OPTIONS.keys())
            for app_name in apps:
                result.append({
                    'name': app_name,
                    'path': sh.joinpths(self.bindir, app_name),
                })
        else:
            for short_name in self.component_opts:
                full_name = SUB_COMPONENT_NAME_MAP.get(short_name)
                if full_name and full_name in APP_OPTIONS:
                    result.append({
                        'name': full_name,
                        'path': sh.joinpths(self.bindir, full_name),
                    })
        return result

    def pre_start(self):
        # Let the parent class do its thing
        comp.PythonRuntime.pre_start(self)
        virt_driver = _canon_virt_driver(self.cfg.get('nova', 'virt_driver'))
        if virt_driver == virsh.VIRT_TYPE:
            virt_type = _canon_libvirt_type(self.cfg.get('nova', 'libvirt_type'))
            LOG.info("Checking that your selected libvirt virtualization type [%s] is working and running." % (virt_type))
            if not virsh.virt_ok(virt_type, self.distro):
                msg = ("Libvirt type %s for distro %s does not seem to be active or configured correctly, "
                       "perhaps you should be using %s instead." % (virt_type, self.distro, DEF_VIRT_TYPE))
                raise exceptions.StartException(msg)
            virsh.restart(self.distro)

    def _get_param_map(self, app_name):
        params = comp.PythonRuntime._get_param_map(self, app_name)
        params['CFGFILE'] = sh.joinpths(self.cfgdir, API_CONF)
        return params

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)


#this will configure nova volumes which in a developer box
#is a volume group (lvm) that are backed by a loopback file
class NovaVolumeConfigurator(object):
    def __init__(self, ni):
        self.cfg = ni.cfg
        self.appdir = ni.appdir

    def setup_volumes(self):
        self._setup_vol_groups()

    def _setup_vol_groups(self):
        LOG.info("Attempting to setup volume groups for nova volume management.")
        mp = dict()
        backing_file = self.cfg.get('nova', 'volume_backing_file')
        # check if we need to have a default backing file
        if not backing_file:
            backing_file = sh.joinpths(self.appdir, 'nova-volumes-backing-file')
        vol_group = self.cfg.get('nova', 'volume_group')
        backing_file_size = utils.to_bytes(self.cfg.get('nova', 'volume_backing_file_size'))
        mp['VOLUME_GROUP'] = vol_group
        mp['VOLUME_BACKING_FILE'] = backing_file
        mp['VOLUME_BACKING_FILE_SIZE'] = backing_file_size
        try:
            utils.execute_template(*VG_CHECK_CMD, params=mp)
            LOG.warn("Volume group already exists: %s" % (vol_group))
        except exceptions.ProcessExecutionError as err:
            # Check that the error from VG_CHECK is an expected error
            if err.exit_code != 5:
                raise
            LOG.info("Need to create volume group: %s" % (vol_group))
            sh.touch_file(backing_file, die_if_there=False, file_size=backing_file_size)
            vg_dev_result = utils.execute_template(*VG_DEV_CMD, params=mp)
            if vg_dev_result and vg_dev_result[0]:
                LOG.debug("VG dev result: %s" % (vg_dev_result))
                # Strip the newlines out of the stdout (which is in the first
                # element of the first (and only) tuple in the response
                (sysout, _) = vg_dev_result[0]
                mp['DEV'] = sysout.replace('\n', '')
                utils.execute_template(*VG_CREATE_CMD, params=mp)
        # One way or another, we should have the volume group, Now check the
        # logical volumes
        self._process_lvs(mp)
        # Finish off by restarting tgt, and ignore any errors
        utils.execute_template(*RESTART_TGT_CMD, check_exit_code=False)

    def _process_lvs(self, mp):
        LOG.info("Attempting to setup logical volumes for nova volume management.")
        lvs_result = utils.execute_template(*VG_LVS_CMD, params=mp)
        if lvs_result and lvs_result[0]:
            LOG.debug("LVS result: %s" % (lvs_result))
            vol_name_prefix = self.cfg.getdefaulted('nova', 'volume_name_prefix', DEF_VOL_PREFIX)
            LOG.debug("Using volume name prefix: %s" % (vol_name_prefix))
            (sysout, _) = lvs_result[0]
            for stdout_line in sysout.split('\n'):
                stdout_line = stdout_line.strip()
                if stdout_line:
                    # Ignore blank lines
                    LOG.debug("Processing LVS output line: %s" % (stdout_line))
                    if stdout_line.startswith(vol_name_prefix):
                        # TODO still need to implement the following:
                        # tid=`egrep "^tid.+$lv" /proc/net/iet/volume | cut -f1 -d' ' | tr ':' '='`
                        # if [[ -n "$tid" ]]; then
                        #   lun=`egrep "lun.+$lv" /proc/net/iet/volume | cut -f1 -d' ' | tr ':' '=' | tr -d '\t'`
                        #   sudo ietadm --op delete --$tid --$lun
                        # fi
                        # sudo lvremove -f $VOLUME_GROUP/$lv
                        raise NotImplementedError("LVS magic not yet implemented!")
                    mp['LV'] = stdout_line
                    utils.execute_template(*VG_LVREMOVE_CMD, params=mp)


# This class has the smarts to build the configuration file based on
# various runtime values. A useful reference for figuring out this
# is at http://docs.openstack.org/diablo/openstack-compute/admin/content/ch_configuring-openstack-compute.html
class NovaConfConfigurator(object):
    def __init__(self, ni):
        self.cfg = ni.cfg
        self.instances = ni.instances
        self.component_root = ni.component_root
        self.appdir = ni.appdir
        self.tracewriter = ni.tracewriter
        self.paste_conf_fn = ni.paste_conf_fn
        self.distro = ni.distro
        self.cfgdir = ni.cfgdir
        self.xvnc_enabled = ni.xvnc_enabled
        self.volumes_enabled = ni.volumes_enabled
        self.novnc_enabled = utils.service_enabled(settings.NOVNC, self.instances)

    def _getbool(self, name):
        return self.cfg.getboolean('nova', name)

    def _getstr(self, name, default=''):
        return self.cfg.getdefaulted('nova', name, default)

    def configure(self):
        #everything built goes in here
        nova_conf = NovaConf()

        #used more than once
        hostip = self.cfg.get('host', 'ip')

        #verbose on?
        if self._getbool('verbose'):
            nova_conf.add_simple('verbose')

        # Check if we have a logdir specified. If we do, we'll make
        # sure that it exists. We will *not* use tracewrite because we
        # don't want to lose the logs when we uninstall
        logdir = self._getstr('logdir')
        if logdir:
            full_logdir = sh.abspth(logdir)
            nova_conf.add('logdir', full_logdir)
            # Will need to be root to create it since it may be in /var/log
            if not sh.isdir(full_logdir):
                LOG.debug("Making sure that nova logdir exists at: %s" % full_logdir)
                with sh.Rooted(True):
                    sh.mkdir(full_logdir)
                    sh.chmod(full_logdir, 0777)

        #allow the admin api?
        if self._getbool('allow_admin_api'):
            nova_conf.add_simple('allow_admin_api')

        #??
        nova_conf.add_simple('allow_resize_to_same_host')

        #which scheduler do u want?
        nova_conf.add('scheduler_driver', self._getstr('scheduler', DEF_SCHEDULER))

        #setup network settings
        self._configure_network_settings(nova_conf)

        #setup nova volume settings
        if self.volumes_enabled:
            self._configure_vols(nova_conf)

        #where we are running
        nova_conf.add('my_ip', hostip)

        #setup your sql connection
        nova_conf.add('sql_connection', self.cfg.get_dbdsn('nova'))

        #configure anything libvirt releated?
        virt_driver = _canon_virt_driver(self._getstr('virt_driver'))
        if virt_driver == virsh.VIRT_TYPE:
            libvirt_type = _canon_libvirt_type(self._getstr('libvirt_type'))
            self._configure_libvirt(libvirt_type, nova_conf)

        #how instances will be presented
        instance_template = self._getstr('instance_name_prefix') + self._getstr('instance_name_postfix')
        if not instance_template:
            instance_template = DEF_INSTANCE_TEMPL
        nova_conf.add('instance_name_template', instance_template)

        #enable the standard extensions
        nova_conf.add('osapi_compute_extension', STD_COMPUTE_EXTS)

        #vnc settings setup
        self._configure_vnc(nova_conf)

        #where our paste config is
        nova_conf.add('api_paste_config', self.paste_conf_fn)

        #what our imaging service will be
        self._configure_image_service(nova_conf, hostip)

        #ec2 / s3 stuff
        nova_conf.add('ec2_dmz_host', self._getstr('ec2_dmz_host', hostip))
        nova_conf.add('s3_host', hostip)

        #how is your rabbit setup?
        nova_conf.add('rabbit_host', self.cfg.get('default', 'rabbit_host'))
        nova_conf.add('rabbit_password', self.cfg.get("passwords", "rabbit"))

        #where instances will be stored
        instances_path = self._getstr('instances_path', sh.joinpths(self.component_root, 'instances'))
        self._configure_instances_path(instances_path, nova_conf)

        #is this a multihost setup?
        self._configure_multihost(nova_conf)

        #enable syslog??
        self._configure_syslog(nova_conf)

        #handle any virt driver specifics
        self._configure_virt_driver(nova_conf)

        #and extract to finish
        return self._get_content(nova_conf)

    def _get_content(self, nova_conf):
        generated_content = nova_conf.generate()
        extra_flags = self._getstr('extra_flags')
        if extra_flags:
            new_contents = list()
            new_contents.append(generated_content)
            #Lines that start with a # are ignored as comments.
            #Leading whitespace is also ignored in flagfiles, as are blank lines.
            new_contents.append("")
            new_contents.append("# Extra FLAGS")
            new_contents.append("")
            cleaned_lines = list()
            extra_lines = extra_flags.splitlines()
            for line in extra_lines:
                cleaned_line = line.strip()
                if len(cleaned_line):
                    cleaned_lines.append(cleaned_line)
            #anything actually found?
            if cleaned_lines:
                new_contents.extend(cleaned_lines)
                generated_content = utils.joinlinesep(*new_contents)
        return generated_content

    def _configure_image_service(self, nova_conf, hostip):
        #what image service we will use
        img_service = self._getstr('img_service', DEF_IMAGE_SERVICE)
        nova_conf.add('image_service', img_service)

        #where is glance located?
        if img_service.lower().find("glance") != -1:
            glance_api_server = self._getstr('glance_server', (DEF_GLANCE_SERVER % (hostip)))
            nova_conf.add('glance_api_servers', glance_api_server)

    def _configure_vnc(self, nova_conf):
        if self.novnc_enabled:
            nova_conf.add('novncproxy_base_url', self._getstr('vncproxy_url'))

        if self.xvnc_enabled:
            nova_conf.add('xvpvncproxy_base_url', self._getstr('xvpvncproxy_url'))

        nova_conf.add('vncserver_listen', self._getstr('vncserver_listen', VNC_DEF_ADDR))

        # If no vnc proxy address was specified,
        # pick a default based on which
        # driver we're using.
        vncserver_proxyclient_address = self._getstr('vncserver_proxyclient_address')
        if not vncserver_proxyclient_address:
            drive_canon = _canon_virt_driver(self._getstr('virt_driver'))
            if drive_canon == 'xenserver':
                vncserver_proxyclient_address = XS_VNC_ADDR
            else:
                vncserver_proxyclient_address = VNC_DEF_ADDR

        nova_conf.add('vncserver_proxyclient_address', vncserver_proxyclient_address)

    def _configure_vols(self, nova_conf):
        nova_conf.add('volume_group', self._getstr('volume_group'))
        vol_name_tpl = self._getstr('volume_name_prefix') + self._getstr('volume_name_postfix')
        if not vol_name_tpl:
            vol_name_tpl = DEF_VOL_TEMPL
        nova_conf.add('volume_name_template', vol_name_tpl)
        nova_conf.add('iscsi_help', 'tgtadm')

    def _configure_network_settings(self, nova_conf):
        #TODO this might not be right....
        if utils.service_enabled(settings.QUANTUM, self.instances, False):
            nova_conf.add('network_manager', QUANTUM_MANAGER)
            nova_conf.add('quantum_connection_host', self.cfg.get('quantum', 'q_host'))
            nova_conf.add('quantum_connection_port', self.cfg.get('quantum', 'q_port'))
            if self.cfg.get('quantum', 'q_plugin') == 'openvswitch':
                for (key, value) in QUANTUM_OPENSWITCH_OPS.items():
                    if value is None:
                        nova_conf.add_simple(key)
                    else:
                        nova_conf.add(key, value)
            if utils.service_enabled(settings.MELANGE_CLIENT, self.instances, False):
                nova_conf.add('quantum_ipam_lib', QUANTUM_IPAM_LIB)
                nova_conf.add_simple('use_melange_mac_generation')
                nova_conf.add('melange_host', self.cfg.get('melange', 'm_host'))
                nova_conf.add('melange_port', self.cfg.get('melange', 'm_port'))
        else:
            nova_conf.add('network_manager', NET_MANAGER_TEMPLATE % (self._getstr('network_manager', DEF_NET_MANAGER)))

        #dhcp bridge stuff???
        nova_conf.add('dhcpbridge_flagfile', sh.joinpths(self.cfgdir, API_CONF))

        #Network prefix for the IP network that all the projects for future VM guests reside on. Example: 192.168.0.0/12
        nova_conf.add('fixed_range', self._getstr('fixed_range'))

        # The value for vlan_interface may default to the the current value
        # of public_interface. We'll grab the value and keep it handy.
        public_interface = self._getstr('public_interface')
        vlan_interface = self._getstr('vlan_interface', public_interface)

        #do a little check to make sure actually have that interface set...
        if not utils.is_interface(public_interface):
            msg = "Public interface %s is not a known interface" % (public_interface)
            raise exceptions.ConfigException(msg)

        if not utils.is_interface(vlan_interface):
            msg = "VLAN interface %s is not a known interface" % (vlan_interface)
            raise exceptions.ConfigException(msg)

        nova_conf.add('public_interface', public_interface)
        nova_conf.add('vlan_interface', vlan_interface)

        #This forces dnsmasq to update its leases table when an instance is terminated.
        nova_conf.add_simple('force_dhcp_release')

    def _configure_syslog(self, nova_conf):
        if self.cfg.getboolean('default', 'syslog'):
            nova_conf.add_simple('use_syslog')

    def _configure_multihost(self, nova_conf):
        if self._getbool('multi_host'):
            nova_conf.add_simple('multi_host')
            nova_conf.add_simple('send_arp_for_ha')

    def _configure_instances_path(self, instances_path, nova_conf):
        nova_conf.add('instances_path', instances_path)
        LOG.debug("Attempting to create instance directory: %s" % (instances_path))
        self.tracewriter.make_dir(instances_path)
        LOG.debug("Adjusting permissions of instance directory: %s" % (instances_path))
        os.chmod(instances_path, 0777)

    def _configure_libvirt(self, virt_type, nova_conf):
        if virt_type == 'lxc':
            #TODO need to add some goodies here
            pass
        nova_conf.add('libvirt_type', virt_type)

    #configures any virt driver settings
    def _configure_virt_driver(self, nova_conf):
        drive_canon = _canon_virt_driver(self._getstr('virt_driver'))
        nova_conf.add('connection_type', VIRT_DRIVER_CON_MAP.get(drive_canon, drive_canon))
        #special driver settings
        if drive_canon == 'xenserver':
            nova_conf.add('xenapi_connection_url', self._getstr('xa_connection_url', XA_DEF_CONNECTION_URL))
            nova_conf.add('xenapi_connection_username', self._getstr('xa_connection_username', XA_DEF_USER))
            nova_conf.add('xenapi_connection_password', self.cfg.get("passwords", "xenapi_connection"))
            nova_conf.add_simple('noflat_injected')
            xs_flat_ifc = self._getstr('xs_flat_interface', XS_DEF_INTERFACE)
            if not utils.is_interface(xs_flat_ifc):
                msg = "Xenserver flat interface %s is not a known interface" % (xs_flat_ifc)
                raise exceptions.ConfigException(msg)
            nova_conf.add('flat_interface', xs_flat_ifc)
            nova_conf.add('firewall_driver', self._getstr('xs_firewall_driver', DEF_FIREWALL_DRIVER))
            nova_conf.add('flat_network_bridge', self._getstr('xs_flat_network_bridge', XS_DEF_BRIDGE))
        elif drive_canon == virsh.VIRT_TYPE:
            nova_conf.add('firewall_driver', self._getstr('libvirt_firewall_driver', DEF_FIREWALL_DRIVER))
            nova_conf.add('flat_network_bridge', self._getstr('flat_network_bridge', DEF_FLAT_VIRT_BRIDGE))
            flat_interface = self._getstr('flat_interface')
            if flat_interface:
                if not utils.is_interface(flat_interface):
                    msg = "Libvirt flat interface %s is not a known interface" % (flat_interface)
                    raise exceptions.ConfigException(msg)
                nova_conf.add('flat_interface', flat_interface)


# This class represents the data in the nova config file
class NovaConf(object):
    def __init__(self):
        self.lines = list()

    def add_list(self, key, *params):
        self.lines.append({'key': key, 'options': params})
        LOG.debug("Added nova conf key %s with values [%s]" % (key, ",".join(params)))

    def add_simple(self, key):
        self.lines.append({'key': key, 'options': None})
        LOG.debug("Added nova conf key %s" % (key))

    def add(self, key, value):
        self.lines.append({'key': key, 'options': [value]})
        LOG.debug("Added nova conf key %s with value [%s]" % (key, value))

    def _form_key(self, key, has_opts):
        key_str = "--" + str(key)
        if has_opts:
            key_str += "="
        return key_str

    def generate(self, param_dict=None):
        conf_lines = sorted(self._generate_lines(param_dict))
        full_lines = list()
        full_lines.append("# Generated on %s" % (date.rcf8222date()))
        full_lines.extend(conf_lines)
        return utils.joinlinesep(*full_lines)

    def _generate_lines(self, param_dict=None):
        gen_lines = list()
        for line_entry in self.lines:
            key = line_entry.get('key')
            opts = line_entry.get('options')
            if not key:
                continue
            if opts is None:
                key_str = self._form_key(key, False)
                full_line = key_str
            else:
                key_str = self._form_key(key, True)
                filled_opts = utils.param_replace_list(opts, param_dict)
                full_line = key_str + ",".join(filled_opts)
            gen_lines.append(full_line)
        return gen_lines
