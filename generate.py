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
        logging.debug("Ensuring that storage directory '{0}' exists".format(self.base_dir))
        os.makedirs(self.base_dir, exist_ok=True)

    def get_base_dir(self):
        return self.base_dir

    def get_full_path(self, relative_path):
        return "{0}/{1}".format(self.base_dir, relative_path)

    def write_file(self, relative_path, content, overwrite):
        full_path = self.get_full_path(relative_path)
        directory = os.path.dirname(full_path)
        os.makedirs(directory, exist_ok=True)
        if not overwrite and os.path.isfile(full_path):
            logging.warn("File {0} exists and overwrite disabled, skipping".format(full_path))
            return

        logging.info("Saving content to {0}".format(full_path))
        with open(full_path, "w") as f:
            f.write(content)

    def set_permissions(self, relative_path, perms):
        full_path = self.get_full_path(relative_path)
        logging.debug("Setting permissions {0} to {1}".format(perms, full_path))
        os.chmod(full_path, int(perms, 8))

class Archive:

    def __init__(self, name, storage):
        self.storage = storage
        self.name = name
        self.file_list = {}

    def get_full_path(self, relative_path):
        return "{0}{1}".format(self.name, relative_path)

    def store(self, relative_path, content, perms, overwrite):
        full_path = self.get_full_path(relative_path)
        self.file_list[relative_path] = True
        self.storage.write_file(full_path, content, overwrite)
        self.storage.set_permissions(full_path, perms)

    def make_tar(self):
        archive_path = self.storage.get_full_path("{0}.tar.gz".format(self.name))
        with tarfile.open(archive_path, "w:gz") as tar:
            for relative_path in self.file_list:
                full_path = self.storage.get_full_path(self.get_full_path(relative_path))
                tar.add(full_path, arcname=relative_path)
                logging.debug("File {0} added to tarball".format(full_path))
            logging.debug("Tarball {0} created".format(archive_path))

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
            self.secured_flags = struct["secured_flags"]
            self.standard_flags = struct["standard_flags"]
            self.shell_flags = struct["shell_flags"]

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
        logging.info("Loading configuration file {0}".format(relative_path))
        directory_name = os.path.dirname(relative_path)
        if len(directory_name) > 0:
            logging.debug("Adding '{0}' to system path".format(directory_name))
            sys.path.insert(0, directory_name)
        file_name = os.path.basename(relative_path)
        module_name = os.path.splitext(file_name)[0]
        logging.debug("Loading module {0} from file {1} located in {2}".format(module_name, file_name, directory_name))
        module = importlib.import_module(module_name)

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

    def __init__(self, storage, template_directory, overwrite_keys, overwrite_zones):
        self.storage = storage
        self.overwrite_keys = overwrite_keys
        self.overwrite_zones = overwrite_zones

        self.template_lookup = mako.lookup.TemplateLookup(directories=[template_directory])

        self.archives = {}
        self.setup_archive("master-conf")
        self.setup_archive("master-zones")
        self.setup_archive("slave-conf")

    def setup_archive(self, name):
        self.archives[name] = Archive(name, self.storage)

    def get_template(self, name):
        return self.template_lookup.get_template(name)

    def save(self, archive, inner_directory, file_name, content, perms, overwrite):
        if isinstance(archive, str):
            self.archives[archive].store("{0}/{1}".format(inner_directory, file_name), content, perms, overwrite)
        elif isinstance(archive, list):
            for arch in archive:
                self.archives[arch].store("{0}/{1}".format(inner_directory, file_name), content, perms, overwrite)
        else:
            raise TypeError("Argument 'archive' of must be either a string or a list of string")

    def run(self, config):

        file = "named.conf"
        logging.debug("Rendering {0}".format(file))
        r = self.get_template(file).render(config=config)
        self.save(["master-conf", "slave-conf"], config.path.config, file, r, config.secured_permissions.standard_flags, True)

        file = "named.conf.options"
        logging.debug("Rendering {0}".format(file))
        r = self.get_template(file).render(config=config)
        self.save(["master-conf", "slave-conf"], config.path.config, file, r, config.secured_permissions.standard_flags, True)

        file = "auth-master-slave.key"
        logging.debug("Rendering (auth) key '{0}'".format(file))
        r = self.get_template("key").render(key=RandomKey("master-slave"))
        self.save(["master-conf", "slave-conf"], config.path.config, file, r, config.secured_permissions.secured_flags, self.overwrite_keys)

        file = "named.conf.local.master"
        logging.debug("Rendering {0}".format(file))
        r = self.get_template(file).render(config=config)
        self.save("master-conf", config.path.config, "named.conf.local", r, config.secured_permissions.standard_flags, True)

        file = "named.conf.local.slave"
        logging.debug("Rendering {0}".format(file))
        r = self.get_template(file).render(config=config)
        self.save("slave-conf", config.path.config, "named.conf.local", r, config.secured_permissions.standard_flags, True)

        file = "secure_permissions.sh"
        logging.debug("Rendering {0}".format(file))
        r = self.get_template(file).render(config=config)
        self.save(["master-conf", "slave-conf"], config.path.config, file, r, config.secured_permissions.shell_flags, True)

        file = "ensure_dnssec_keys.sh"
        logging.debug("Rendering {0}".format(file))
        r = self.get_template(file).render(config=config)
        self.save("master-conf", config.path.config, file, r, config.secured_permissions.shell_flags, True)

        for zone in config.zones.values():

            file = "zone_file"
            logging.debug("Rendering {0} for {1}".format(file, zone.name))
            r = self.get_template(file).render(config=config, zone=zone)
            self.save("master-zones", config.path.data, "db.{0}".format(zone.name), r, config.secured_permissions.standard_flags, self.overwrite_zones)

            for d_u in zone.dynamic_updates.values():

                n = "{0}.{1}".format(d_u.name, zone.name)
                file = "nsupdate-keys/{0}/{1}.key".format(zone.name, n)
                logging.debug("Rendering (dynamic-update) key {0}".format(n))
                r = self.get_template("key").render(key=RandomKey(n))
                self.save("master-conf", config.path.config, file, r, config.secured_permissions.secured_flags, self.overwrite_keys)

        file = "install.sh"
        logging.debug("Rendering {0}".format(file))
        r = self.get_template(file).render(config=config, build_dir=self.storage.base_dir)
        self.storage.write_file(file, r, True)
        self.storage.set_permissions(file, config.secured_permissions.shell_flags)

        for archive in self.archives.values():
            archive.make_tar()

if __name__ == '__main__':
    try:
        # analyze commande line arguments
        parser = argparse.ArgumentParser(description="Bind9 configuration generator")
        parser.add_argument("-c", "--config-file", metavar="CFG", default="config.py")
        parser.add_argument("-d", "--destination", metavar="DST_DIR", default="build")
        parser.add_argument("-t", "--templates", metavar="SRC_DIR", default="templates")
        parser.add_argument("-l", "--log-level", metavar="LVL", choices=["critical", "error", "warning", "info", "debug"], default="warning")
        parser.add_argument("--overwrite-keys", action="store_true")
        parser.add_argument("--overwrite-zones", action="store_true")
        args = parser.parse_args()

        # configure logging
        numeric_level = getattr(logging, args.log_level.upper())
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=numeric_level)
        logging.debug("Command line arguments: {0}".format(args))

        # setup environment
        cfg = Configuration(args.config_file)
        storage = Storage(args.destination)

        # work
        app = App(storage, args.templates, args.overwrite_keys, args.overwrite_zones)
        app.run(cfg)

    except Exception as e:
        logging.error("{0}: {1}".format(e.__class__.__name__, e))
