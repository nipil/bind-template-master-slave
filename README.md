# bind-template-master-slave

A MAKO template for quick generation of master/slave Bind9 configurations

Note, this template is modular and follows the Debian/Ubuntu file organisation

It is mostly useful for initialization (as zone files are pushed and will overwrite existing ones)

# Setup

On your management environment :

    apt-get install python3 python3-venv
    python3 -m venv venv
    . venv/bin/activate
    pip install wheel
    pip install -r requirements.txt

# Use

Edit the first part of `generate.py` to fit your needs

Run :

    . venv/bin/activate
    ./generate.py

Options:

    -l level : specify logging level (default=warning)
    -c config.py : use specified configuration files
    -d destination : folder where all the generated files will be placed
    -t templates : folder where the templates are located
    -f : overwrite key files and zone files

# Install

For each slave dns server :

- push `build/slave-conf.tar.gz` to the host
- install it : `tar xfv slave-conf.tar.gz -C /`
- fix permissions : `${CONF_DIR}/secure_permissions.sh`
- reload configuration : `rndc reconfig`

On your master server :

- push `build/master-conf.tar.gz` and `build/master-zones.tar.gz` to the host
- stop bind : `systemctl stop bind9`
- install config `tar xfv master-conf.tar.gz -C /`
- install zones files (without overwriting existing ones, for example) `tar xfv master-conf.tar.gz -C / --keep-old-files`
- fix permissions : `${CONF_DIR}/secure_permissions.sh`
- ensure DNSSEC keys are setup : `${CONF_DIR}/ensure_dnssec_keys.sh`
- start bind : `systemctl start bind9`
