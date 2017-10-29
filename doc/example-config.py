config = {
    "path": {
        "config": "/etc/bind",
        "data": "/var/cache/bind",
    },
    "secured_permissions": {
        "root-user": "root",
        "bind-user": "bind",
        "bind-group": "bind",
        "secured_flags": "640",
        "standard_flags": "664",
    },
    "master": {
        "fqdn": "ns1.example.com",
        "ipv4": "192.0.2.1",
        "ipv6": "2001:db8:0:1::1",
    },
    "slaves": {
        "ns2.example.com": {
            "ipv4": "198.51.100.1",
            "ipv6": "2001:db8:0:2::1",
        },
        "ns3.example.com": {
            "ipv4": "203.0.113.1",
            "ipv6": "2001:db8:0:3::1",
        },
    },
    "zones": {
        "example.org": {
            "dynamic-updates": {
                "laptop": "A AAAA",
                "home-server": "ANY",
            },
        },
        "example.com": {
            "dynamic-updates": {
                "test": "A",
            }
        },
        "example.net": {},
        "example.edu": {},
        "example.biz": {},
    },
    "parameters": {
        "email": "hostmaster@example.com",
        "ttl": "5m",
        "refresh": "4h",
        "retry": "1h",
        "expire": "1w",
        "minimum": "3h",
    },
}
