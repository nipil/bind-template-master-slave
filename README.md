# bind-template-master-slave

A MAKO template for quick generation of master/slave Bind9 configurations

Note, this template is modular and follows the Debian/Ubuntu file organisation

It is mostly useful for initialization and reconfiguration (as zone files are always "almost empty")

# Setup

On your management environment :

    apt-get install python3 python3-venv
    python3 -m venv venv
    . venv/bin/activate
    pip install wheel
    pip install -r requirements.txt

# Local usage

Edit the first part of `generate.py` to fit your needs

Run :

    . venv/bin/activate
    ./generate.py config.py

Where `config.py` (or any other name) is a python script holding the desired configuration (see `doc/example-config.py` for the required structure)

Options:

    -l level : specify logging level (default=warning)
    -d destination : folder where all the generated files will be placed
    -t templates : folder where the templates are located
    -f : overwrite key files and zone files
    --overwrite-keys : will overwrite key files (which are preserved by default)
    --overwrite-zones : will overwrite zone files (which are preserved by default)

# Remote install

For each slave dns server :

- push `build/slave-conf.tar.gz` to the host
- install it : `tar xfv slave-conf.tar.gz -C /`
- fix permissions : `${CONF_DIR}/secure_permissions.sh`
- reload configuration : `rndc reconfig`

On your master server :

- push `build/master-conf.tar.gz` and `build/master-zones.tar.gz` to the host
- stop bind : `systemctl stop bind9`
- install config `tar xfv master-conf.tar.gz -C /`
- install zones files `tar xfv master-conf.tar.gz -C / --keep-old-files`
- fix permissions : `${CONF_DIR}/secure_permissions.sh`
- ensure DNSSEC keys are setup : `${CONF_DIR}/ensure_dnssec_keys.sh`
- start bind : `systemctl start bind9`

# Remote install script

The tool generates an remote install script `build/install.sh`. This script requires a valid ssh configuration for each master/slave fqdn, with a user which can run all commands (root). It uploads the files via SCP and runs the commands remotely.

If your installation method differs, adapt the install script in the template folder

# Example of use

Let's say you are managing a few clusters of dns servers (a cluster being a group consisting of 1 master and 1+ slaves) and you name them RED, BLUE, and GREEN. RED and BLUE have direct ssh access (for installation), while GREEN has no SSH access (it's an LXD container with only file access throught LXD file facility from the host managing the containers). Furthermore, BLUE doesn't do DNSSEC, while the others do.

One way you could manage your clusters with in the situation above :

- clone/fork this repository once
- copy the templates folder 3 times, one for each cluster, name them "template-X" where X is the cluster name
- copy the example config 3 times, one for each cluster, name them "config-X.py" where X is the cluster name
- adapt the configurations to each cluster (network topology, defined zones, allowed update-policy)
- adapt the template folder to each cluster (bind configuration and installation method)
- use distinct `build-X` folder for each cluster
- then run `generate.py` with appropriate `-c`, `-t`, and `-d` flags to update

For example, the modifications for BLUE :

- disable DNSSEC in templates
- update `install.sh` to remove the `ensure_dnssec.sh` call

For example, the modifications for GREEN :

- update `install.sh` to add some "lxd file ..." to the mix

In all cases :

- commit the per-cluster templates to the repository
- commit the per-cluster configuration to the repository
- commit the build folder to the repository

NOTE: Commiting the build directories might sound counter-intuitive, but this ensures that you can revert to the installed/previous keys/zones in case of mistaken `-f` use

NOTE: you could clone/fork this repo once per cluster too, instead of putting all your eggs in one repo :-)

# One step further

The generated zones contain only a basic declaration, facilitating new zone installation (hence the serial 0). Once they are generated and installed, your server will live its life and the zones on the master server will be populated, thus going out of sync with the zones generated in this repo.

This is why the install script uses `--keep-old-files` for tar extraction of the zone archive : only new zone files will be installed on target server. This is not a mistake, this is by design, as the present tool is only a helper to *bootstrap* things for data (zones) and simplify management (configuration + keys).

One way to deal with this fact is to install a hook on the master server, watching bind log file for zone updates, then trigger a zone transfer of the modified zones, and finally commits the zone to the a local git repo. That way you holda copy of each and every revision of each zone. Once this is done, you could link both repo (the repo holding the up-to-date zone data, and the present repo) which would allows for the inclusion of the up-to-date zones in the shipped archives.
