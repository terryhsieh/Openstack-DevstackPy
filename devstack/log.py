# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Copyright 2011 OpenStack LLC.
#    All Rights Reserved.
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

import functools
import logging
import pprint

from logging.handlers import SysLogHandler
from logging.handlers import WatchedFileHandler

# A list of things we want to replicate from logging levels
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
WARN = logging.WARN
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

# methods
getLogger = logging.getLogger
debug = logging.debug
info = logging.info
warning = logging.warning
warn = logging.warn
error = logging.error
exception = logging.exception
critical = logging.critical
log = logging.log

# classes
root = logging.root
Formatter = logging.Formatter

# handlers
StreamHandler = logging.StreamHandler
WatchedFileHandler = WatchedFileHandler
SysLogHandler = SysLogHandler


def log_debug(f):
    @functools.wraps(f)
    def wrapper(*args, **kw):
        if root.isEnabledFor(debug):
            logging.debug('%s(%s, %s) ->', f.func_name, str(args), str(kw))
        rv = f(*args, **kw)
        if root.isEnabledFor(debug):
            logging.debug(pprint.pformat(rv, indent=2))
            logging.debug('')
        return rv
    return wrapper
