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

import io
import time

from devstack import cfg
from devstack import component as comp
from devstack import date
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import utils

from devstack.components import db
from devstack.components import keystone

from devstack.image import creator

#id
TYPE = settings.GLANCE
LOG = logging.getLogger("devstack.components.glance")

#config files/sections
#during the transition for glance to the split config files
#we cat them together to handle both pre- and post-merge
API_CONF = "glance-api.conf"
REG_CONF = "glance-registry.conf"
API_PASTE_CONF = 'glance-api-paste.ini'
REG_PASTE_CONF = 'glance-registry-paste.ini'
LOGGING_CONF = "logging.conf"
LOGGING_SOURCE_FN = 'logging.cnf.sample'
POLICY_JSON = 'policy.json'
CONFIGS = [API_CONF, REG_CONF, API_PASTE_CONF,
            REG_PASTE_CONF, POLICY_JSON, LOGGING_CONF]
READ_CONFIGS = [API_CONF, REG_CONF, API_PASTE_CONF, REG_PASTE_CONF]

#reg, api are here as possible subcomponents
GAPI = "api"
GREG = "reg"

#this db will be dropped and created
DB_NAME = "glance"

#special subcomponents/options that are used in starting to know that images should be uploaded
NO_IMG_START = "no-image-upload"
WAIT_ONLINE_TO = settings.WAIT_ALIVE_SECS

#what to start
APP_OPTIONS = {
    'glance-api': ['--config-file', sh.joinpths('%ROOT%', "etc", API_CONF)],
    'glance-registry': ['--config-file', sh.joinpths('%ROOT%', "etc", REG_CONF)]
}

#how the subcompoent small name translates to an actual app
SUB_TO_APP = {
    GAPI: 'glance-api',
    GREG: 'glance-registry'
}

#subdirs of the downloaded
CONFIG_DIR = 'etc'
BIN_DIR = 'bin'

#the pkg json files glance requires for installation
REQ_PKGS = ['general.json', 'glance.json']

#pip files that glance requires
REQ_PIPS = ['general.json', 'glance.json']


class GlanceUninstaller(comp.PythonUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)


class GlanceInstaller(comp.PythonInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PythonInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)

    def _get_download_locations(self):
        places = list()
        places.append({
            'uri': ("git", "glance_repo"),
            'branch': ("git", "glance_branch"),
        })
        return places

    def _get_config_files(self):
        return list(CONFIGS)

    def _get_pips(self):
        return list(REQ_PIPS)

    def _get_pkgs(self):
        return list(REQ_PKGS)

    def post_install(self):
        comp.PythonInstallComponent.post_install(self)
        self._setup_db()

    def _setup_db(self):
        LOG.info("Fixing up database named %s.", DB_NAME)
        db.drop_db(self.cfg, DB_NAME)
        db.create_db(self.cfg, DB_NAME)

    def _get_source_config(self, config_fn):
        if config_fn == API_CONF:
            (fn, top) = utils.load_template(self.component_name, API_CONF)
            (_, bottom) = self._get_source_config(API_PASTE_CONF)
            combined = [top, "### Joined here on %s with file %s" % (date.rcf8222date(), API_PASTE_CONF), bottom]
            return (fn, utils.joinlinesep(*combined))
        elif config_fn == REG_CONF:
            (fn, top) = utils.load_template(self.component_name, REG_CONF)
            (_, bottom) = self._get_source_config(REG_PASTE_CONF)
            combined = [top, "### Joined here on %s with file %s" % (date.rcf8222date(), REG_PASTE_CONF), bottom]
            return (fn, utils.joinlinesep(*combined))
        elif config_fn == POLICY_JSON:
            fn = sh.joinpths(self.cfgdir, POLICY_JSON)
            contents = sh.load_file(fn)
            return (fn, contents)
        elif config_fn == LOGGING_CONF:
            fn = sh.joinpths(self.cfgdir, LOGGING_SOURCE_FN)
            contents = sh.load_file(fn)
            return (fn, contents)
        return comp.PythonInstallComponent._get_source_config(self, config_fn)

    def _config_adjust(self, contents, name):
        #even bother opening??
        if name not in READ_CONFIGS:
            return contents
        #use config parser and
        #then extract known configs that
        #will need locations/directories/files made (or touched)...
        with io.BytesIO(contents) as stream:
            config = cfg.IgnoreMissingConfigParser()
            config.readfp(stream)
            if config.getboolean('default', 'image_cache_enabled'):
                cache_dir = config.get('default', "image_cache_datadir")
                if cache_dir:
                    LOG.info("Ensuring image cache data directory %s exists "\
                             "(and is empty)" % (cache_dir))
                    #destroy then recreate the image cache directory
                    sh.deldir(cache_dir)
                    self.tracewriter.make_dir(cache_dir)
            if config.get('default', 'default_store') == 'file':
                file_dir = config.get('default', 'filesystem_store_datadir')
                if file_dir:
                    LOG.info("Ensuring file system store directory %s exists and is empty." % (file_dir))
                    #delete existing images
                    #and recreate the image directory
                    sh.deldir(file_dir)
                    self.tracewriter.make_dir(file_dir)
            log_filename = config.get('default', 'log_file')
            if log_filename:
                LOG.info("Ensuring log file %s exists and is empty." % (log_filename))
                log_dir = sh.dirname(log_filename)
                if log_dir:
                    LOG.info("Ensuring log directory %s exists." % (log_dir))
                    self.tracewriter.make_dir(log_dir)
                #destroy then recreate it (the log file)
                sh.unlink(log_filename)
                sh.touch_file(log_filename)
                self.tracewriter.file_touched(log_filename)
            if config.getboolean('default', 'delayed_delete'):
                data_dir = config.get('default', 'scrubber_datadir')
                if data_dir:
                    LOG.info("Ensuring scrubber data dir %s exists and is empty." % (data_dir))
                    #destroy then recreate the scrubber data directory
                    sh.deldir(data_dir)
                    self.tracewriter.make_dir(data_dir)
            #we might need to handle more in the future...
        #nothing modified so just return the original
        return contents

    def _get_param_map(self, config_fn):
        #this dict will be used to fill in the configuration
        #params with actual values
        mp = dict()
        mp['DEST'] = self.appdir
        mp['SYSLOG'] = self.cfg.getboolean("default", "syslog")
        mp['SQL_CONN'] = self.cfg.get_dbdsn(DB_NAME)
        mp['SERVICE_HOST'] = self.cfg.get('host', 'ip')
        mp['HOST_IP'] = self.cfg.get('host', 'ip')
        mp.update(keystone.get_shared_params(self.cfg))
        return mp


class GlanceRuntime(comp.PythonRuntime):
    def __init__(self, *args, **kargs):
        comp.PythonRuntime.__init__(self, TYPE, *args, **kargs)
        self.cfgdir = sh.joinpths(self.appdir, CONFIG_DIR)

    def _get_apps_to_start(self):
        apps = list()
        if not self.component_opts:
            for app_name in APP_OPTIONS.keys():
                apps.append({
                    'name': app_name,
                    'path': sh.joinpths(self.appdir, BIN_DIR, app_name),
                })
        else:
            for short_name in self.component_opts:
                full_name = SUB_TO_APP.get(short_name)
                if full_name and full_name in APP_OPTIONS:
                    apps.append({
                        'name': full_name,
                        'path': sh.joinpths(self.appdir, BIN_DIR, full_name),
                    })
        return apps

    def _get_app_options(self, app):
        return APP_OPTIONS.get(app)

    def post_start(self):
        comp.PythonRuntime.post_start(self)
        if NO_IMG_START not in self.component_opts:
            #install any images that need activating...
            # TODO: make this less cheesy - need to wait till glance goes online
            LOG.info("Waiting %s seconds so that glance can start up before image install." % (WAIT_ONLINE_TO))
            time.sleep(WAIT_ONLINE_TO)
            creator.ImageCreationService(self.cfg).install()
