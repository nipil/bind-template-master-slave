#!/bin/sh
echo ${config.master.fqdn}
% for slave in config.slaves.values():
echo ${slave.fqdn}
% endfor
