#!/bin/sh

find ${config.path.config} -type f -print0 \
| xargs -0 -I FILES sh -c \
'chown ${config.secured_permissions.root_user}:${config.secured_permissions.bind_group} FILES ;'

find ${config.path.config} -maxdepth 1 -type f -name '*.key' -print0 \
| xargs -0 -I FILES sh -c \
'chmod ${config.secured_permissions.secured_flags} FILES ;'

find ${config.path.data} -type f -print0 \
| xargs -0 -I FILES sh -c \
'chown ${config.secured_permissions.bind_user}:${config.secured_permissions.bind_group} FILES ;'
