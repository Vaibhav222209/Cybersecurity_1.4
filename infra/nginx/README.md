# Reverse proxy plan

Phase 2 will configure local HTTPS entry, a reviewed TLS 1.3 configuration, bounded requests, rate limits, response headers, explicit API/OIDC routes, and upstream service authentication. Bind published ports to loopback; do not expose management interfaces. Test real proxy requests and certificate rejection cases before claiming readiness.
