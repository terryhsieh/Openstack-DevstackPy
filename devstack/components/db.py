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

import time

from devstack import component as comp
from devstack import exceptions as excp
from devstack import log as logging
from devstack import settings
from devstack import shell as sh
from devstack import trace as tr
from devstack import utils

#id
TYPE = settings.DB
LOG = logging.getLogger("devstack.components.db")

#used for special setups
MYSQL = 'mysql'
START_WAIT_TIME = settings.WAIT_ALIVE_SECS

#TODO maybe we should handle this differently in the future, blah
#ie in a special set of classes (make this class abstract)...
DB_ACTIONS = {
    MYSQL: {
        # Of course these aren't distro independent...
        'runtime': {
            settings.UBUNTU11: {
                'start': ["service", "mysql", 'start'],
                'stop': ["service", 'mysql', "stop"],
                'status': ["service", 'mysql', "status"],
                'restart': ["service", 'mysql', "restart"],
            },
            settings.RHEL6: {
                'start': ["service", "mysqld", 'start'],
                'stop': ["service", 'mysqld', "stop"],
                'status': ["service", 'mysqld', "status"],
                'restart': ["service", 'mysqld', "restart"],
            },
            settings.FEDORA16: {
                'start': ["service", "mysqld", 'start'],
                'stop': ["service", 'mysqld', "stop"],
                'status': ["service", 'mysqld', "status"],
                'restart': ["service", 'mysqld', "restart"],
            },
        },
        #modification commands
        #NOTE: we aren't stopping any sql injection...
        'set_pwd': ['mysql', '--user=%USER%', '--password=%OLD_PASSWORD%', '-e',
                    ("\"USE mysql; UPDATE user SET "
                    " password=PASSWORD('%NEW_PASSWORD%') WHERE User='%USER%'; FLUSH PRIVILEGES;\"")],
        'create_db': ['mysql', '--user=%USER%', '--password=%PASSWORD%',
                      '-e', 'CREATE DATABASE %DB%;'],
        'drop_db': ['mysql', '--user=%USER%', '--password=%PASSWORD%',
                    '-e', 'DROP DATABASE IF EXISTS %DB%;'],
        'grant_all': ["mysql", "--user=%USER%", "--password=%PASSWORD%", '-e',
                    ("\"GRANT ALL PRIVILEGES ON *.* TO '%USER%'@'%' "
                    " IDENTIFIED BY '%PASSWORD%'; FLUSH PRIVILEGES;\"")],
    },
}

#need to reset pw to blank since this distributions don't seem to always reset it when u uninstall the db
RESET_BASE_PW = ''

#links about how to reset if it fails
SQL_RESET_PW_LINKS = ['https://help.ubuntu.com/community/MysqlPasswordReset',
                      'http://dev.mysql.com/doc/refman/5.0/en/resetting-permissions.html']

#used as a generic error message
BASE_ERROR = 'Currently we do not know how to [%s] for database type [%s]'

#the pkg json files db requires for installation
REQ_PKGS = ['db.json']

#config keys we warm up so u won't be prompted later
WARMUP_PWS = ['sql']


class DBUninstaller(comp.PkgUninstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgUninstallComponent.__init__(self, TYPE, *args, **kargs)
        self.runtime = DBRuntime(*args, **kargs)

    def warm_configs(self):
        for pw_key in WARMUP_PWS:
            self.cfg.get("passwords", pw_key)

    def pre_uninstall(self):
        dbtype = self.cfg.get("db", "type")
        dbactions = DB_ACTIONS.get(dbtype)
        try:
            if dbactions:
                LOG.info(("Attempting to reset your db password to \"%s\" so"
                          " that we can set it the next time you install.") % (RESET_BASE_PW))
                pwd_cmd = dbactions.get('set_pwd')
                if pwd_cmd:
                    LOG.info("Ensuring your database is started before we operate on it.")
                    self.runtime.restart()
                    user = self.cfg.get("db", "sql_user")
                    old_pw = self.cfg.get("passwords", 'sql')
                    params = {
                        'OLD_PASSWORD': old_pw,
                        'NEW_PASSWORD': RESET_BASE_PW,
                        'USER': user,
                        }
                    cmds = [{'cmd': pwd_cmd}]
                    utils.execute_template(*cmds, params=params, shell=True)
        except IOError:
            LOG.warn(("Could not reset the database password. You might have to manually "
                      "reset the password to \"%s\" before the next install") % (RESET_BASE_PW))
            LOG.info("To aid in this check out: [%s]", " or ".join(SQL_RESET_PW_LINKS))


class DBInstaller(comp.PkgInstallComponent):
    def __init__(self, *args, **kargs):
        comp.PkgInstallComponent.__init__(self, TYPE, *args, **kargs)
        self.runtime = DBRuntime(*args, **kargs)

    def _get_param_map(self, config_fn):
        #this dictionary will be used for parameter replacement
        #in pre-install and post-install sections
        host_ip = self.cfg.get('host', 'ip')
        out = {
            'PASSWORD': self.cfg.get("passwords", "sql"),
            'BOOT_START': ("%s" % (True)).lower(),
            'USER': self.cfg.get("db", "sql_user"),
            'SERVICE_HOST': host_ip,
            'HOST_IP': host_ip
        }
        return out

    def warm_configs(self):
        for pw_key in WARMUP_PWS:
            self.cfg.get("passwords", pw_key)

    def _configure_db_confs(self):
        dbtype = self.cfg.get("db", "type")
        #TODO: maybe this should be a subclass that handles these differences
        if self.distro == settings.RHEL6 and dbtype == MYSQL:
            LOG.info("Fixing up %s mysql configs." % (settings.RHEL6))
            fc = sh.load_file('/etc/my.cnf')
            lines = fc.splitlines()
            new_lines = list()
            for line in lines:
                if line.startswith('skip-grant-tables'):
                    line = '#' + line
                new_lines.append(line)
            fc = utils.joinlinesep(*new_lines)
            with sh.Rooted(True):
                sh.write_file('/etc/my.cnf', fc)
        elif self.distro == settings.UBUNTU11 and dbtype == MYSQL:
            LOG.info("Fixing up %s mysql configs." % (settings.UBUNTU11))
            fc = sh.load_file('/etc/mysql/my.cnf')
            lines = fc.splitlines()
            new_lines = list()
            for line in lines:
                if line.startswith('bind-address'):
                    line = 'bind-address = %s' % ('0.0.0.0')
                new_lines.append(line)
            fc = utils.joinlinesep(*new_lines)
            with sh.Rooted(True):
                sh.write_file('/etc/mysql/my.cnf', fc)

    def _get_pkgs(self):
        return list(REQ_PKGS)

    def post_install(self):
        comp.PkgInstallComponent.post_install(self)

        #fix up the db configs
        self._configure_db_confs()

        #extra actions to ensure we are granted access
        dbtype = self.cfg.get("db", "type")
        dbactions = DB_ACTIONS.get(dbtype)

        #set your password
        try:
            if dbactions:
                pwd_cmd = dbactions.get('set_pwd')
                if pwd_cmd:
                    LOG.info(("Attempting to set your db password"
                          " just incase it wasn't set previously."))
                    LOG.info("Ensuring your database is started before we operate on it.")
                    self.runtime.restart()
                    params = {
                        'NEW_PASSWORD': self.cfg.get("passwords", "sql"),
                        'USER': self.cfg.get("db", "sql_user"),
                        'OLD_PASSWORD': RESET_BASE_PW,
                        }
                    cmds = [{'cmd': pwd_cmd}]
                    utils.execute_template(*cmds, params=params, shell=True)
        except IOError:
            LOG.warn(("Couldn't set your db password. It might have already been "
                       "set by a previous process."))

        #ensure access granted
        if dbactions:
            grant_cmd = dbactions.get('grant_all')
            if grant_cmd:
                user = self.cfg.get("db", "sql_user")
                LOG.info("Updating the DB to give user '%s' full control of all databases." % (user))
                LOG.info("Ensuring your database is started before we operate on it.")
                self.runtime.restart()
                params = {
                    'PASSWORD': self.cfg.get("passwords", "sql"),
                    'USER': user,
                }
                cmds = list()
                cmds.append({
                    'cmd': grant_cmd,
                })
                #shell seems to be needed here
                #since python escapes this to much...
                utils.execute_template(*cmds, params=params, shell=True)


class DBRuntime(comp.EmptyRuntime):
    def __init__(self, *args, **kargs):
        comp.EmptyRuntime.__init__(self, TYPE, *args, **kargs)
        self.tracereader = tr.TraceReader(self.tracedir, tr.IN_TRACE)

    def _get_run_actions(self, act, exception_cls):
        dbtype = self.cfg.get("db", "type")
        type_actions = DB_ACTIONS.get(dbtype)
        if type_actions is None:
            msg = BASE_ERROR % (act, dbtype)
            raise NotImplementedError(msg)
        distro_options = type_actions.get('runtime').get(self.distro)
        if distro_options is None:
            msg = BASE_ERROR % (act, dbtype)
            raise NotImplementedError(msg)
        return distro_options.get(act)

    def start(self):
        if self.status() != comp.STATUS_STARTED:
            startcmd = self._get_run_actions('start', excp.StartException)
            sh.execute(*startcmd,
                run_as_root=True,
                check_exit_code=True)
            LOG.info("Please wait %s seconds while it starts up." % START_WAIT_TIME)
            time.sleep(START_WAIT_TIME)
            return 1
        else:
            return 0

    def stop(self):
        if self.status() != comp.STATUS_STOPPED:
            stopcmd = self._get_run_actions('stop', excp.StopException)
            sh.execute(*stopcmd,
                run_as_root=True,
                check_exit_code=True)
            return 1
        else:
            return 0

    def restart(self):
        LOG.info("Restarting your database.")
        restartcmd = self._get_run_actions('restart', excp.RestartException)
        sh.execute(*restartcmd,
                        run_as_root=True,
                        check_exit_code=True)
        LOG.info("Please wait %s seconds while it restarts." % START_WAIT_TIME)
        time.sleep(START_WAIT_TIME)
        return 1

    def status(self):
        statuscmd = self._get_run_actions('status', excp.StatusException)
        run_result = sh.execute(*statuscmd,
                            run_as_root=True,
                            check_exit_code=False)
        if not run_result:
            return comp.STATUS_UNKNOWN
        (sysout, stderr) = run_result
        combined = str(sysout) + str(stderr)
        combined = combined.lower()
        if combined.find("running") != -1:
            return comp.STATUS_STARTED
        elif combined.find("stop") != -1:
            return comp.STATUS_STOPPED
        else:
            return comp.STATUS_UNKNOWN


def drop_db(cfg, dbname):
    dbtype = cfg.get("db", "type")
    dbactions = DB_ACTIONS.get(dbtype)
    if dbactions and dbactions.get('drop_db'):
        dropcmd = dbactions.get('drop_db')
        params = dict()
        params['PASSWORD'] = cfg.get("passwords", "sql")
        params['USER'] = cfg.get("db", "sql_user")
        params['DB'] = dbname
        cmds = list()
        cmds.append({
            'cmd': dropcmd,
            'run_as_root': False,
        })
        utils.execute_template(*cmds, params=params)
    else:
        msg = BASE_ERROR % ('drop', dbtype)
        raise NotImplementedError(msg)


def create_db(cfg, dbname):
    dbtype = cfg.get("db", "type")
    dbactions = DB_ACTIONS.get(dbtype)
    if dbactions and dbactions.get('create_db'):
        createcmd = dbactions.get('create_db')
        params = dict()
        params['PASSWORD'] = cfg.get("passwords", "sql")
        params['USER'] = cfg.get("db", "sql_user")
        params['DB'] = dbname
        cmds = list()
        cmds.append({
            'cmd': createcmd,
            'run_as_root': False,
        })
        utils.execute_template(*cmds, params=params)
    else:
        msg = BASE_ERROR % ('create', dbtype)
        raise NotImplementedError(msg)
