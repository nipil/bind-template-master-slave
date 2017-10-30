#!/usr/bin/env bash

set -e

if [[ "$1" == "remote" ]]
then
% for slave in config.slaves.values():
    scp ${build_dir}/slave-conf.tar.gz ${build_dir}/install.sh ${slave.fqdn}:/tmp
    ssh ${slave.fqdn} '/tmp/install.sh slave && rm -f /tmp/slave-conf.tar.gz /tmp/install.sh'

% endfor
    scp ${build_dir}/master-conf.tar.gz ${build_dir}/master-zones.tar.gz ${build_dir}/install.sh ${config.master.fqdn}:/tmp
    ssh ${config.master.fqdn} '/tmp/install.sh master'
fi

if [[ "$1" == "master" || "$1" == "slave" ]]
then
    systemctl stop bind9
    tar -x -f /tmp/$1-conf.tar.gz -C /
fi

if [[ "$1" == "slave" ]]
then
    rm -f ${config.path.data}/db.*
fi

if [[ "$1" == "master" ]]
then
    for z in $(tar -t -f /tmp/$1-zones.tar.gz)
    do
        [ ! -e /$z ] || { echo "Skipping $z zone file as it exists"; continue; }
        tar -x -v -f /tmp/$1-zones.tar.gz -C / $z
    done
fi

if [[ "$1" == "master" || "$1" == "slave" ]]
then
    ${config.path.config}/secure_permissions.sh
fi

if [[ "$1" == "master" ]]
then
    ${config.path.config}/ensure_dnssec_keys.sh
fi

if [[ "$1" == "master" || "$1" == "slave" ]]
then
    systemctl start bind9
fi
