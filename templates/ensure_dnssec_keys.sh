#!/bin/sh

% for zone in config.zones.values():
TARGET=${config.path.config}/dnssec-keys/${zone.name}

mkdir -p $TARGET

find $TARGET -type f -name 'K*.key' -print0 \
    | xargs -0 grep "key-signing key" > /dev/null

[ $? -eq 0 ] || {
    echo "Missing key-signing key for ${zone.name}" ;
    dnssec-keygen -K $TARGET -f ksk ${zone.name} ;
}

find $TARGET -type f -name 'K*.key' -print0 \
    | xargs -0 grep "zone-signing key" > /dev/null

[ $? -eq 0 ] || {
    echo "Missing zone signing key for ${zone.name}" ;
    dnssec-keygen -K $TARGET ${zone.name} ;
}

%endfor

find ${config.path.config}/dnssec-keys -type f -name '*.private' -print0 \
| xargs -0 -I FILES sh -c \
'chown ${config.secured_permissions.root_user}:${config.secured_permissions.bind_group} FILES ; chmod ${config.secured_permissions.secured_flags} FILES ;'
