#!/usr/bin/env python3

# --------------------------------------------------------------------------
# edit templates below if you really require it
# --------------------------------------------------------------------------

all_templates = {

"named.conf": '''
// This is the primary configuration file for the BIND DNS server named.
//
// Please read /usr/share/doc/bind9/README.Debian.gz for information on the
// structure of BIND configuration files in Debian, *BEFORE* you customize
// this configuration file.
//
// If you are just adding zones, please do that in ${CONFIG_DIR}/named.conf.local

include "/${CONFIG_DIR}/named.conf.options";
include "/${CONFIG_DIR}/named.conf.local";
include "/${CONFIG_DIR}/named.conf.default-zones";
''',

# --------------------------------------------------------------------------

"named.conf.options": '''

options {
    directory "/${DATA_DIR}";

    // If there is a firewall between you and nameservers you want
    // to talk to, you may need to fix the firewall to allow multiple
    // ports to talk.  See http://www.kb.cert.org/vuls/id/800113

    // If BIND logs error messages about the root key being expired,
    // you will need to update your keys.  See https://www.isc.org/bind-keys
    dnssec-validation auto;

    auth-nxdomain no; # conform to RFC1035
    listen-on-v6 { any; };

    allow-query { any; };
    allow-query-cache { none; };
    allow-transfer { none; };
    recursion no;
    minimal-responses yes;
    // minimal-any yes; // Bind 9.11
};
''',

# --------------------------------------------------------------------------

"key": '''
key "${KEY_NAME}" {
    algorithm ${KEY_ALGO};
    secret "${KEY_SECRET}";
};
''',

# --------------------------------------------------------------------------

"named.conf.local.master": '''
<%
    def get_dynamic_updates(zone_data):
        try:
            return zone_data["dynamic-updates"]
        except KeyError:
            return {}
%>
//
// Do any local configuration here
//

// --------------------------------------------------------------------------
// SECURITY
// --------------------------------------------------------------------------

// auth key for master-slave communications
include "/${CONFIG_DIR}/auth-master-slave.key";

% for SLAVE_FQDN, SLAVE_ADDRESSES in SLAVES.items():
// authenticate communications with ${SLAVE_FQDN}
server ${SLAVE_ADDRESSES["ipv4"]} {
    keys { master-slave ; };
};
server ${SLAVE_ADDRESSES["ipv6"]} {
    keys { master-slave ; };
};

% endfor
% for ZONE_NAME, ZONE_DATA in ZONES.items():
// --------------------------------------------------------------------------
// ${ZONE_NAME}
// --------------------------------------------------------------------------

% if len(get_dynamic_updates(ZONE_DATA)) > 0:
// nsupdate keys for ${ZONE_NAME}
    % for RR_NAME, RR_TYPES in get_dynamic_updates(ZONE_DATA).items():
include "/${CONFIG_DIR}/nsupdate-keys/${ZONE_NAME}/${RR_NAME}.${ZONE_NAME}.key";
    %endfor

% endif
zone "${ZONE_NAME}" {
    type master;
    file "/${DATA_DIR}/db.${ZONE_NAME}";
    allow-transfer { key master-slave ; };

    key-directory "/${CONFIG_DIR}/dnssec-keys/${ZONE_NAME}";
    inline-signing yes;
    auto-dnssec maintain;
    % if len(get_dynamic_updates(ZONE_DATA)) > 0:

    update-policy {
        grant local-ddns zonesub any;
        % for RR_NAME, RR_TYPES in get_dynamic_updates(ZONE_DATA).items():
        grant ${RR_NAME}.${ZONE_NAME} self * ${RR_TYPES};
        % endfor
    };
    % endif
};

%endfor
''',

# --------------------------------------------------------------------------

"named.conf.local.slave": '''
//
// Do any local configuration here
//

// --------------------------------------------------------------------------
// SECURITY
// --------------------------------------------------------------------------

// auth key for master-slave communications
include "/${CONFIG_DIR}/auth-master-slave.key";

// authenticate communications with ${MASTER["fqdn"]}
server ${MASTER["ipv4"]} {
    keys { master-slave ; };
};
server ${MASTER["ipv6"]} {
    keys { master-slave ; };
};

% for ZONE_NAME, ZONE_DATA in ZONES.items():
// --------------------------------------------------------------------------
// ${ZONE_NAME}
// --------------------------------------------------------------------------

zone "${ZONE_NAME}" {

    type slave;
    file "/${DATA_DIR}/db.${ZONE_NAME}";
    masters {
        ${MASTER["ipv4"]};
        ${MASTER["ipv6"]};
    };
};

%endfor
''',

# --------------------------------------------------------------------------

"zone_file": '''
<%
import re
%>
$ORIGIN ${ZONE_NAME}.
$TTL ${PARAMETERS["ttl"]}
@ IN SOA ${MASTER["fqdn"]}. ${PARAMETERS["email"].replace("@",".")}. (
    0 ; serial
    ${PARAMETERS["refresh"]} ; refresh
    ${PARAMETERS["retry"]} ; retry
    ${PARAMETERS["expire"]} ; expire
    ${PARAMETERS["minimum"]} ; minimum
    )
@ IN NS ${MASTER["fqdn"]}.
% if re.match('^.*\.%s$' % ZONE_NAME, MASTER["fqdn"]):
${MASTER["fqdn"]}. IN A ${MASTER["ipv4"]}
${MASTER["fqdn"]}. IN AAAA ${MASTER["ipv6"]}
% endif
% for SLAVE_FQDN, SLAVE_ADDRESSES in SLAVES.items():
@ IN NS ${SLAVE_FQDN}.
    % if re.match('^.*\.%s$' % ZONE_NAME, SLAVE_FQDN):
${SLAVE_FQDN}. IN A ${SLAVE_ADDRESSES["ipv4"]}
${SLAVE_FQDN}. IN AAAA ${SLAVE_ADDRESSES["ipv6"]}
    % endif
% endfor
''',

# --------------------------------------------------------------------------

"secure_permissions.sh": '''#!/bin/sh

find /${CONFIG_DIR} -type f -print0 \
| xargs -0 -I FILES sh -c \
'chown ${PERMISSIONS["root-user"]}:${PERMISSIONS["bind-group"]} FILES ;'

find /${CONFIG_DIR} -maxdepth 1 -type f -name '*.key' -print0 \
| xargs -0 -I FILES sh -c \
'chmod ${PERMISSIONS["flags"]} FILES ;'

find /${DATA_DIR} -type f -print0 \
| xargs -0 -I FILES sh -c \
'chown ${PERMISSIONS["bind-user"]}:${PERMISSIONS["bind-group"]} FILES ;'
''',

# --------------------------------------------------------------------------

"ensure_dnssec_keys.sh": '''#!/bin/sh

% for ZONE_NAME, ZONE_DATA in ZONES.items():
TARGET=/${CONFIG_DIR}/dnssec-keys/${ZONE_NAME}

mkdir -p $TARGET

find $TARGET -type f -name 'K*.key' -print0 \
    | xargs -0 grep "key-signing key" > /dev/null

[ $? -eq 0 ] || {
    echo "Missing key-signing key for ${ZONE_NAME}" ;
    dnssec-keygen -K $TARGET -f ksk ${ZONE_NAME} ;
}

find $TARGET -type f -name 'K*.key' -print0 \
    | xargs -0 grep "zone-signing key" > /dev/null

[ $? -eq 0 ] || {
    echo "Missing zone signing key for ${ZONE_NAME}" ;
    dnssec-keygen -K $TARGET ${ZONE_NAME} ;
}

%endfor

find /${CONFIG_DIR}/dnssec-keys -type f -name '*.private' -print0 \
| xargs -0 -I FILES sh -c \
'chown ${PERMISSIONS["root-user"]}:${PERMISSIONS["bind-group"]} FILES ; chmod ${PERMISSIONS["flags"]} FILES ;'

''',

# --------------------------------------------------------------------------

"install.sh": '''#!/bin/sh
echo ${MASTER["fqdn"]}
% for SLAVE_FQDN in SLAVES:
echo ${SLAVE_FQDN}
% endfor
''',

}

# --------------------------------------------------------------------------
# you do not need to edit what is below this comment
# --------------------------------------------------------------------------

import argparse
import base64
import logging
import os
import os.path
import random
import re
import stat
import sys
import tarfile

import importlib
import mako.template

class Storage:

    def __init__(self, base_dir):
        self.base_dir = base_dir
        logging.debug("Ensuring that storage directory '%s' exists" % self.base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def get_base_dir(self):
        return self.base_dir

    def get_full_path(self, relative_path):
        return "%s/%s" % (self.base_dir, relative_path)

    def write_file(self, relative_path, content, overwrite):
        full_path = self.get_full_path(relative_path)
        directory = os.path.dirname(full_path)
        os.makedirs(directory, exist_ok=True)
        if not overwrite and os.path.isfile(full_path):
            logging.info("File %s exists and overwrite disabled, skipping" % full_path)
            return

        logging.debug("Saving content to %s" % full_path)
        with open(full_path, "w") as f:
            f.write(content)

    def set_permissions(self, relative_path, perms):
        full_path = self.get_full_path(relative_path)
        logging.debug("Setting permissions %s to %s" % (perms, full_path))
        os.chmod(full_path, int(perms, 8))

class Archive:

    def __init__(self, name, storage):
        self.storage = storage
        self.name = name
        self.file_list = {}

    def get_full_path(self, relative_path):
        return "%s/%s" % (self.name, relative_path)

    def store(self, relative_path, content, perms, overwrite):
        full_path = self.get_full_path(relative_path)
        self.file_list[relative_path] = True
        self.storage.write_file(full_path, content, overwrite)
        self.storage.set_permissions(full_path, perms)

    def make_tar(self):
        archive_path = self.storage.get_full_path("%s.tar.gz" % self.name)
        with tarfile.open(archive_path, "w:gz") as tar:
            for relative_path in self.file_list:
                full_path = self.storage.get_full_path(self.get_full_path(relative_path))
                tar.add(full_path, arcname=relative_path)
                logging.debug("File %s added to tarball" % full_path)
            logging.debug("Tarball %s created" % archive_path)

class Configuration:

    def __init__(self, relative_path):
        self.load(relative_path)

    def load(self, relative_path):
        logging.info("Loading configuration file %s" % relative_path)
        directory_name = os.path.dirname(relative_path)
        if len(directory_name) > 0:
            logging.debug("Adding '%s' to system path" % directory_name)
            sys.path.insert(0, directory_name)
        file_name = os.path.basename(relative_path)
        module_name = os.path.splitext(file_name)[0]
        logging.debug("Loading module %s from file %s located in %s" % (module_name, file_name, directory_name))
        module = importlib.import_module(module_name)
        self.config = module.config

    def get_config_path(self):
        return self.config["path"]["config"]

    def get_data_path(self):
        return self.config["path"]["data"]

    def get_zones(self):
        return self.config["zones"]

    def get_master(self):
        return self.config["master"]

    def get_slaves(self):
        return self.config["slaves"]

    def get_parameters(self):
        return self.config["parameters"]

    def get_secured_permissions(self):
        return self.config["secured_permissions"]

class App:

    def __init__(self, storage, overwrite):
        self.storage = storage
        self.archives = {}
        self.setup_archive("master-conf")
        self.setup_archive("master-zones")
        self.setup_archive("slave-conf")
        self.overwrite = overwrite

    def setup_archive(self, name):
        self.archives[name] = Archive(name, self.storage)

    @staticmethod
    def get_random_base64(length):
        r = random.SystemRandom()
        d = bytes([r.randint(0, 255) for i in range(length)])
        return base64.b64encode(d).decode("UTF-8")

    def save(self, archive, inner_directory, file_name, content, perms="664"):
        self.archives[archive].store("%s/%s" % (inner_directory, file_name), content, perms, self.overwrite)

    def run(self, config, templates):

        # named.conf
        t = mako.template.Template(templates["named.conf"])
        r = t.render(CONFIG_DIR=config.get_config_path())
        self.save("master-conf", config.get_config_path(), "named.conf", r)
        self.save("slave-conf", config.get_config_path(), "named.conf", r)
        # named.conf.options
        t = mako.template.Template(templates["named.conf.options"])
        r = t.render(DATA_DIR=config.get_data_path())
        self.save("master-conf", config.get_config_path(), "named.conf.options", r)
        self.save("slave-conf", config.get_config_path(), "named.conf.options", r)
        # named.conf.options
        t = mako.template.Template(templates["key"])
        r = t.render(
            KEY_NAME="master-slave",
            KEY_ALGO="hmac-sha256",
            KEY_SECRET=self.get_random_base64(32))
        self.save("master-conf", config.get_config_path(), "auth-master-slave.key", r, "640")
        self.save("slave-conf", config.get_config_path(), "auth-master-slave.key", r, "640")
        # named.conf.local.master
        t = mako.template.Template(templates["named.conf.local.master"])
        r = t.render(
            CONFIG_DIR=config.get_config_path(),
            DATA_DIR=config.get_data_path(),
            SLAVES=config.get_slaves(),
            ZONES=config.get_zones())
        self.save("master-conf", config.get_config_path(), "named.conf.local", r)
        # named.conf.local.slave
        t = mako.template.Template(templates["named.conf.local.slave"])
        r = t.render(
            CONFIG_DIR=config.get_config_path(),
            DATA_DIR=config.get_data_path(),
            MASTER=config.get_master(),
            ZONES=config.get_zones())
        self.save("slave-conf", config.get_config_path(), "named.conf.local", r)

        # permission script
        t = mako.template.Template(templates["secure_permissions.sh"])
        r = t.render(
            CONFIG_DIR=config.get_config_path(),
            DATA_DIR=config.get_data_path(),
            PERMISSIONS=config.get_secured_permissions(),
            ZONES=config.get_zones())
        self.save("master-conf", config.get_config_path(), "secure_permissions.sh", r)
        self.save("slave-conf", config.get_config_path(), "secure_permissions.sh", r)
        # dnssec-key script
        t = mako.template.Template(templates["ensure_dnssec_keys.sh"])
        r = t.render(
            CONFIG_DIR=config.get_config_path(),
            PERMISSIONS=config.get_secured_permissions(),
            ZONES=config.get_zones())
        self.save("master-conf", config.get_config_path(), "ensure_dnssec_keys.sh", r)

        # per zone stuff
        for zone_name, zone_data in config.get_zones().items():

            # zone file
            t = mako.template.Template(templates["zone_file"])
            r = t.render(
                PARAMETERS=config.get_parameters(),
                MASTER=config.get_master(),
                SLAVES=config.get_slaves(),
                ZONE_NAME=zone_name)
            self.save("master-zones", config.get_data_path(), "db.%s" % zone_name, r)

            # nsupdate keys
            try:
                nsupdate = zone_data["dynamic-updates"]
            except KeyError:
                nsupdate = {}
            for rr_name in nsupdate:
                t = mako.template.Template(templates["key"])
                r = t.render(
                    KEY_NAME="%s.%s" % (rr_name, zone_name),
                    KEY_ALGO="hmac-sha256",
                    KEY_SECRET=self.get_random_base64(32))
                f = "nsupdate-keys/%s/%s.%s.key" % (zone_name, rr_name, zone_name)
                self.save("master-conf", config.get_config_path(), f, r, "640")

        # generate install script
        t = mako.template.Template(templates["install.sh"])
        r = t.render(MASTER=config.get_master(), SLAVES=config.get_slaves())
        self.storage.write_file("install.sh", r, self.overwrite)

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config-file", metavar="CFG", default="config.py")
    parser.add_argument("-d", "--destination", metavar="DEST", default="build")
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-l", "--log-level", metavar="LVL", choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], default="WARNING")
    args = parser.parse_args()

    numeric_level = getattr(logging, args.log_level)
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=numeric_level)
    logging.debug("Command line arguments: %s" % args)

    if args.force:
        logging.info("Forced mode activated, keys will be overwritten")

    storage = Storage(args.destination)
    app = App(storage, args.force)

    cfg = Configuration(args.config_file)
    app.run(cfg, all_templates)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.error(e)
