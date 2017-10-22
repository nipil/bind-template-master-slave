# bind-template-master-slave

A MAKO template for quick generation of master/slave Bind9 configurations

Note, this template is modular and follows the Debian/Ubuntu file organisation

# Setup

On your management environment :

    apt-get install python3 python3-venv
    python3 -m venv venv
    . venv/bin/activate
    pip install wheel
    pip install -r requirements.txt

# Use

Edit config.py to fit your needs

Run :

    . venv/bin/activate
    ./generate.py

Then install generated files to your servers
