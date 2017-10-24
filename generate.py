#!/usr/bin/env python3

config = {
    "masters": {
        "ns1.example.com": {
            "ipv4": "192.0.2.1",
            "ipv6": "2001:db8:0:1::1",
        },
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

templates = {
    "common": {
        "etc/bind/named.conf": '''
            include "/etc/bind/zones.rfc1918";
            include "/etc/bind/named.conf.options";
            include "/etc/bind/named.conf.local";
            include "/etc/bind/named.conf.default-zones";
        ''',

        "etc/bind/named.conf.default-zones": '''
            // prime the server with knowledge of the root servers
            zone "." {
                    type hint;
                    file "/etc/bind/db.root";
            };

            // be authoritative for the localhost forward and reverse zones, and for
            // broadcast zones as per RFC 1912

            zone "localhost" {
                    type master;
                    file "/etc/bind/db.local";
            };

            zone "127.in-addr.arpa" {
                    type master;
                    file "/etc/bind/db.127";
            };

            zone "0.in-addr.arpa" {
                    type master;
                    file "/etc/bind/db.0";
            };

            zone "255.in-addr.arpa" {
                    type master;
                    file "/etc/bind/db.255";
            };
        ''',
        "etc/bind/named.conf.options": '''
            options {
                    directory "/var/cache/bind";

                    // If BIND logs error messages about the root key
                    // being expired, you will need to update your keys.
                    // See https://www.isc.org/bind-keys
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
        "etc/bind/named.conf.nsupdate-keys": '''
            include "/etc/bind/nsupdate-keys/${KEYNAME}.${ZONE}";
        ''',
        "etc/bind/named.conf.nsupdate-grant": '''
            update-policy {
                grant local-ddns zonesub any;
                grant ${KEYNAME}.${ZONE} self *;
            };
        ''',
        "etc/bind/master-slave.key": '''
            key "master-slave." {
                algorithm hmac-sha256;
                secret "${BASE64SECRET}";
            };
        ''',
    },
    "master": {
        "etc/bind/named.conf.local": '''
            include "/etc/bind/master-slave.key";

            server ${IPV4} {
                keys { master-slave ; };
            };

            server ${IPV6} {
                keys { master-slave ; };
            };

            include "/etc/bind/named.conf.nsupdate-keys";

            zone "${ZONE}" {

                    type master;
                    file "/var/cache/bind/db.${ZONE}";
                    allow-transfer { key master-slave ; };

                    key-directory "/etc/bind/dnssec-keys/${ZONE}";
                    inline-signing yes;
                    auto-dnssec maintain;

                    include "/etc/bind/named.conf.nsupdate-grant";
            };
        '''
    },
    "slave": {
        "etc/bind/named.conf.local": '''
            include "/etc/bind/master-slave.key";

            server ${IPV4} {
                keys { master-slave ; };
            };

            server ${IPV6} {
                keys { master-slave ; };
            };

            zone "${ZONE}" {
                type slave;
                file "/var/cache/bind/db.${ZONE}";
                masters {
                    ${IPV4};
                    ${IPV6};
                };
            };
        '''
    },
}

import argparse
import logging

class App:

    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Generates Bind9 master-slave configurations')
        self.parser.add_argument('-o', '--output-dir', metavar='DIR', default='.')
        self.parser.add_argument('-l', '--log-level', metavar='LVL', type=self.__class__.is_log_level_valid, default='WARNING')

    @staticmethod
    def is_log_level_valid(level_string):
        if level_string.upper() not in { 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL' }:
            raise argparse.ArgumentTypeError('Invalid log level %s' % level_string)
        return level_string.upper()

    def manage_args(self):
        self.args = self.parser.parse_args()
        numeric_level = getattr(logging, self.args.log_level)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=numeric_level)
        logging.debug('Parsed arguments: %s' % self.args)
        logging.info('Output directory is %s' % self.args.output_dir)

    def check_servers(self, servers):
        for fqdn, server in servers.items():
            try:
                ipv4 = server["ipv4"]
            except KeyError as e:
                raise Exception("No ipv4 in server %s" % fqdn)
            try:
                ipv6 = server["ipv6"]
            except KeyError as e:
                raise Exception("No ipv6 in server %s" % fqdn)

    def check_dynamic_update(self, dynamic):
        for name, record_types in dynamic.items():
            if type(record_types) is not str:
                raise Exception("Record type for %s" % name)

    def check_zones(self, zones):
        for name, data in zones.items():
            try:
                dynamic = data["dynamic-updates"]
                self.check_dynamic_update(dynamic)
            except KeyError as e:
                pass

    def check_config(self):
        try:
            servers = config["masters"]
        except KeyError as e:
            raise Exception("No masters in config")
        self.check_servers(servers)
        if len(servers) == 0:
            raise Exception("No servers in masters")
        try:
            servers = config["slaves"]
        except KeyError as e:
            raise Exception("No slaves in config")
        self.check_servers(servers)
        try:
            parameters = config["parameters"]
        except KeyError as e:
            raise Exception("No parameters in config")
        try:
            email = parameters["email"]
        except KeyError as e:
            raise Exception("No email in parameters")
        try:
            ttl = parameters["ttl"]
        except KeyError as e:
            raise Exception("No ttl in parameters")
        try:
            refresh = parameters["refresh"]
        except KeyError as e:
            raise Exception("No refresh in parameters")
        try:
            retry = parameters["retry"]
        except KeyError as e:
            raise Exception("No retry in parameters")
        try:
            expire = parameters["expire"]
        except KeyError as e:
            raise Exception("No expire in parameters")
        try:
            minimum = parameters["minimum"]
        except KeyError as e:
            raise Exception("No minimum in parameters")
        try:
            zones = config["zones"]
        except KeyError as e:
            raise Exception("No zones in config")
        self.check_zones(zones)

    def render_config(self):

        pass

    def run(self):
        self.manage_args()
        self.check_config()
        self.render_config()

if __name__ == '__main__':
    app = App()
    try:
        app.run()
    except Exception as e:
        logging.error("%s: %s" % (e.__class__.__name__, e))
