#!/usr/bin/env python3

import argparse
import base64
import importlib
import logging
import mako.template
import mako.lookup
import os
import os.path
import random
import re
import stat
import sys
import tarfile

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
        return "%s%s" % (self.name, relative_path)

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

    class Path:
        def __init__(self, struct):
            self.config = struct["config"]
            self.data = struct["data"]

    class Master:
        def __init__(self, struct):
            self.fqdn = struct["fqdn"]
            self.ipv4 = struct["ipv4"]
            self.ipv6 = struct["ipv6"]

    class Parameters:
        def __init__(self, struct):
            self.email = struct["email"]
            self.ttl = struct["ttl"]
            self.refresh = struct["refresh"]
            self.retry = struct["retry"]
            self.expire = struct["expire"]
            self.minimum = struct["minimum"]

    class SecuredPermissions:
        def __init__(self, struct):
            self.root_user = struct["root-user"]
            self.bind_user = struct["bind-user"]
            self.bind_group = struct["bind-user"]
            self.flags = struct["flags"]

    class Slave:
        def __init__(self, fqdn, struct):
            self.fqdn = fqdn
            self.ipv4 = struct["ipv4"]
            self.ipv6 = struct["ipv6"]

    class Zone:
        def __init__(self, name, struct):
            self.name = name
            try:
                self.dynamic_updates = {
                    k: Configuration.DynamicUpdate(k, v) for k, v in struct["dynamic-updates"].items()
                }
            except KeyError as e:
                self.dynamic_updates = {}

    class DynamicUpdate:
        def __init__(self, name, types):
            self.name = name
            self.types = types

    def __init__(self, relative_path):
        self.load(relative_path)

    def load(self, relative_path):

        # load from file
        logging.info("Loading configuration file %s" % relative_path)
        directory_name = os.path.dirname(relative_path)
        if len(directory_name) > 0:
            logging.debug("Adding '%s' to system path" % directory_name)
            sys.path.insert(0, directory_name)
        file_name = os.path.basename(relative_path)
        module_name = os.path.splitext(file_name)[0]
        logging.debug("Loading module %s from file %s located in %s" % (module_name, file_name, directory_name))
        module = importlib.import_module(module_name)

        self.config = module.config # TODO: remove

        # parse and store elements
        self.path = Configuration.Path(module.config["path"])
        self.master = Configuration.Master(module.config["master"])
        self.parameters = Configuration.Parameters(module.config["parameters"])
        self.secured_permissions = Configuration.SecuredPermissions(module.config["secured_permissions"])
        self.slaves = {
            k: Configuration.Slave(k, v) for k, v in module.config["slaves"].items()
        }
        self.zones = {
            k: Configuration.Zone(k, v) for k, v in module.config["zones"].items()
        }

class RandomKey:
    def __init__(self, name, algo="hmac-sha256", secret_length=32):
        self.name = name
        self.algo = algo
        r = random.SystemRandom()
        d = bytes([r.randint(0, 255) for i in range(secret_length)])
        self.secret = base64.b64encode(d).decode("UTF-8")

class App:

    def __init__(self, storage, template_directory, force_overwrite):
        self.storage = storage
        self.template_lookup = mako.lookup.TemplateLookup(directories=[template_directory])

        self.archives = {}
        self.setup_archive("master-conf")
        self.setup_archive("master-zones")
        self.setup_archive("slave-conf")
        self.force_overwrite = force_overwrite

    def setup_archive(self, name):
        self.archives[name] = Archive(name, self.storage)

    def get_template(self, name):
        return self.template_lookup.get_template(name)

    def save(self, archive, inner_directory, file_name, content, perms="664", overwrite=True):
        self.archives[archive].store("%s/%s" % (inner_directory, file_name), content, perms, overwrite or self.force_overwrite)

    def run(self, config):

        logging.debug("Rendering %s" % "named.conf")
        r = self.get_template("named.conf").render(config=config)
        self.save("master-conf", config.path.config, "named.conf", r)
        self.save("slave-conf", config.path.config, "named.conf", r)

        logging.debug("Rendering %s" % "named.conf.options")
        r = self.get_template("named.conf.options").render(config=config)
        self.save("master-conf", config.path.config, "named.conf.options", r)
        self.save("slave-conf", config.path.config, "named.conf.options", r)

        logging.debug("Rendering (auth) key '%s'" % "auth-master-slave.key")
        r = self.get_template("key").render(key=RandomKey("master-slave"))
        self.save("master-conf", config.path.config, "auth-master-slave.key", r, "640", False)
        self.save("slave-conf", config.path.config, "auth-master-slave.key", r, "640", False)

        logging.debug("Rendering %s" % "named.conf.local.master")
        r = self.get_template("named.conf.local.master").render(config=config)
        self.save("master-conf", config.path.config, "named.conf.local", r)

        logging.debug("Rendering %s" % "named.conf.local.slave")
        r = self.get_template("named.conf.local.slave").render(config=config)
        self.save("slave-conf", config.path.config, "named.conf.local", r)

        logging.debug("Rendering %s" % "secure_permissions.sh")
        r = self.get_template("secure_permissions.sh").render(config=config)
        self.save("master-conf", config.path.config, "secure_permissions.sh", r)
        self.save("slave-conf", config.path.config, "secure_permissions.sh", r)

        logging.debug("Rendering %s" % "ensure_dnssec_keys.sh")
        r = self.get_template("ensure_dnssec_keys.sh").render(config=config)
        self.save("master-conf", config.path.config, "ensure_dnssec_keys.sh", r)

        for zone in config.zones.values():

            logging.debug("Rendering %s for %s" % ("zone_file", zone.name))
            r = self.get_template("zone_file").render(config=config, zone=zone)
            self.save("master-zones", config.path.data, "db.%s" % zone.name, r)

            for d_u in zone.dynamic_updates.values():
                logging.debug("Rendering (dynamic-update) key '%s' for zone %s" % (d_u.name, zone.name))
                n = "%s.%s" % (d_u.name, zone.name)
                r = self.get_template("key").render(key=RandomKey(n))
                f = "nsupdate-keys/%s/%s.%s.key" % (zone.name, d_u.name, zone.name)
                self.save("master-conf", config.path.config, f, r, "640", False)

        logging.debug("Rendering %s" % "install.sh")
        r = self.get_template("install.sh").render(config=config)
        self.storage.write_file("install.sh", r, True)

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config-file", metavar="CFG", default="config.py")
    parser.add_argument("-d", "--destination", metavar="DST", default="build")
    parser.add_argument("-t", "--templates", metavar="DIR", default="templates")
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-l", "--log-level", metavar="LVL", choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], default="WARNING")
    args = parser.parse_args()

    numeric_level = getattr(logging, args.log_level)
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=numeric_level)
    logging.debug("Command line arguments: %s" % args)

    if args.force:
        logging.info("Forced mode activated, keys will be overwritten")

    storage = Storage(args.destination)
    app = App(storage, args.templates, args.force)

    # data
    cfg = Configuration(args.config_file)

    # work
    app.run(cfg)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.error("%s: %s" % (e.__class__.__name__, e))
