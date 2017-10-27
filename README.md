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

For each slave dns server :

- push `build/slave.tar` to the host
- install it : `tar xfv /root/slave.tar.gz -C /`
- reload configuration : `rndc reconfig`

On your master server :

- push `build/master.tar` to the host
- stop bind : `systemctl stop bind9`
- install config and zone data `tar xfv /root/master.tar.gz -C /`
- start bind : `systemctl start bind9`
