#!/usr/bin/env python3

# --------------------------------------------------------------------------
# edit configuration below to suit your needs
# --------------------------------------------------------------------------

config = {
    "path": {
        # do NOT add any leading /
        "config": "etc/bind",
        "data": "var/cache/bind",
    },
    "secured_permissions": {
        "root-user": "root",
        "bind-user": "bind",
        "bind-group": "bind",
        "flags": "640",
    },
    "master": {
        "fqdn": "ns1.example.com",
        "ipv4": "192.0.2.1",
        "ipv6": "2001:db8:0:1::1",
    },
    "slaves": {
        "ns2.example.com": {
            "ipv4": "198.51.100.1",
            "ipv6": "2001:db8:0:2::1",
        },
        "ns3.example.com": {
            "ipv4": "203.0.113.1",
            "ipv6": "2001:db8:0:3::1",
        },
    },
    "zones": {
        "example.org": {
            "dynamic-updates": {
                "laptop": "A AAAA",
                "home-server": "ANY",
            },
        },
        "example.com": {}
    },
    "parameters": {
        "email": "hostmaster@example.com",
        "ttl": "5m",
        "refresh": "4h",
        "retry": "1h",
        "expire": "1w",
        "minimum": "3h",
    },
}

# --------------------------------------------------------------------------
# edit templates below if you really require it
# --------------------------------------------------------------------------

templates = {

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
}

# --------------------------------------------------------------------------
# you do not need to edit what is below this comment
# --------------------------------------------------------------------------

import base64
import logging
import os
import os.path
import random
import re
import stat
import tarfile

from mako.template import Template

class Archive:

    def __init__(self, archivename, build_dir):
        self.build_dir = build_dir
        os.makedirs(build_dir, exist_ok=True)
        self.archivename = archivename
        self.content = {}
        self.re_key = re.compile("^.*\.key$")
        self.re_shell = re.compile("^.*\.sh$")

    def add(self, filepath, content):
        self.content[filepath] = content

    def save_file(self, fullpath, content):
        if self.re_key.match(fullpath) and os.path.isfile(fullpath):
            logging.warn("File %s exists, not overwriting it" % fullpath)
        elif re.match("^.*/db\.[^.]+(\.[^.]+)+$", fullpath) and os.path.isfile(fullpath):
            logging.warn("File %s exists, not overwriting it" % fullpath)
        else:
            logging.debug("Saving %s" % fullpath)
            with open(fullpath, "w") as f:
                f.write(content)
        # set permissions
        if self.re_key.match(fullpath):
            os.chmod(fullpath,
                stat.S_IRUSR |
                stat.S_IWUSR |
                stat.S_IRGRP |
                stat.S_IWGRP)

        # set permissions
        if self.re_shell.match(fullpath):
            os.chmod(fullpath,
                stat.S_IRUSR |
                stat.S_IWUSR |
                stat.S_IXUSR |
                stat.S_IRGRP |
                stat.S_IWGRP |
                stat.S_IXGRP |
                stat.S_IROTH |
                stat.S_IXOTH)

    def save(self):
        t = "%s/%s.tar.gz" % (self.build_dir, self.archivename)
        with tarfile.open(t, "w:gz") as tar:
            for filepath, content in self.content.items():
                fullpath = "%s/%s/%s" % (self.build_dir, self.archivename, filepath)
                directory = os.path.dirname(fullpath)
                os.makedirs(directory, exist_ok=True)
                self.save_file(fullpath, content)
                tar.add(fullpath, arcname=filepath)
        logging.info("Archive %s ready" % t)

class App:

    def __init__(self, config, templates):
        self.build_dir = "build"
        self.config = config
        self.templates = templates
        # prepare storage
        self.storage = {
            "master-conf": Archive("master-conf", self.build_dir),
            "master-zones": Archive("master-zones", self.build_dir),
            "slave-conf": Archive("slave-conf", self.build_dir),
        }

    @staticmethod
    def get_random_base64(length):
        r = random.SystemRandom()
        d = bytes([r.randint(0, 255) for i in range(length)])
        return base64.b64encode(d).decode("UTF-8")

    def add(self, target, pathtype, relpath, content):
        self.storage[target].add(
            "%s/%s" % (self.config["path"][pathtype], relpath),
            content)

    def get_template(self, name):
        return self.templates[name]

    def save(self):
        for k, v in self.storage.items():
            v.save()

    def run(self):
        t = Template(self.get_template("named.conf"))
        r = t.render(CONFIG_DIR=config["path"]["config"])
        self.add("master-conf", "config", "named.conf", r)
        self.add("slave-conf", "config", "named.conf", r)
        # named.conf.options
        t = Template(self.get_template("named.conf.options"))
        r = t.render(DATA_DIR=config["path"]["data"])
        self.add("master-conf", "config", "named.conf.options", r)
        self.add("slave-conf", "config", "named.conf.options", r)
        # named.conf.options
        t = Template(self.get_template("key"))
        r = t.render(
            KEY_NAME="master-slave",
            KEY_ALGO="hmac-sha256",
            KEY_SECRET=self.get_random_base64(32))
        self.add("master-conf", "config", "auth-master-slave.key", r)
        self.add("slave-conf", "config", "auth-master-slave.key", r)
        # named.conf.local.master
        t = Template(self.get_template("named.conf.local.master"))
        r = t.render(
            CONFIG_DIR=config["path"]["config"],
            DATA_DIR=config["path"]["data"],
            SLAVES=config["slaves"],
            ZONES=config["zones"])
        self.add("master-conf", "config", "named.conf.local", r)
        # named.conf.local.slave
        t = Template(self.get_template("named.conf.local.slave"))
        r = t.render(
            CONFIG_DIR=config["path"]["config"],
            DATA_DIR=config["path"]["data"],
            MASTER=config["master"],
            ZONES=config["zones"])
        self.add("slave-conf", "config", "named.conf.local", r)
        # permission script
        t = Template(self.get_template("secure_permissions.sh"))
        r = t.render(
            CONFIG_DIR=config["path"]["config"],
            DATA_DIR=config["path"]["data"],
            PERMISSIONS=config["secured_permissions"],
            ZONES=config["zones"])
        self.add("master-conf", "config", "secure_permissions.sh", r)
        self.add("slave-conf", "config", "secure_permissions.sh", r)
        # dnssec-key script
        t = Template(self.get_template("ensure_dnssec_keys.sh"))
        r = t.render(
            CONFIG_DIR=config["path"]["config"],
            PERMISSIONS=config["secured_permissions"],
            ZONES=config["zones"])
        self.add("master-conf", "config", "ensure_dnssec_keys.sh", r)
        # per zone stuff
        for zone_name, zone_data in config["zones"].items():
            # zone file
            t = Template(self.get_template("zone_file"))
            r = t.render(
                PARAMETERS=self.config["parameters"],
                MASTER=config["master"],
                SLAVES=config["slaves"],
                ZONE_NAME=zone_name)
            self.add("master-zones", "data", "db.%s" % zone_name, r)
            # nsupdate keys
            try:
                nsupdate = zone_data["dynamic-updates"]
                for rr_name in nsupdate:
                    t = Template(self.get_template("key"))
                    r = t.render(
                        KEY_NAME="%s.%s" % (rr_name, zone_name),
                        KEY_ALGO="hmac-sha256",
                        KEY_SECRET=self.get_random_base64(32))

                    f = "nsupdate-keys/%s/%s.%s.key" % (zone_name, rr_name, zone_name)
                    self.add("master-conf", "config", f, r)
            except KeyError:
                pass
        # generate archives
        self.save()

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    app = App(config, templates)
    app.run()
