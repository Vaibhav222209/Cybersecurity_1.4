# WAF plan

Phase 2 will integrate ModSecurity with a compatible NGINX build and a pinned OWASP Core Rule Set. Verify rule loading, synthetic benign/blocked requests, audit redaction, and bounded logging. WAF coverage supplements application validation; document false positives and any narrowly scoped exceptions. No WAF image or rules are installed in Phase 1.
