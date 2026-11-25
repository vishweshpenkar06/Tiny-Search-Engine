# DNS Resolution and Caching

DNS maps a hostname to an address. A resolver walks from the root through authoritative servers, caching each answer for its time to live.

Caching removes most lookups from the critical path. A low time to live makes changes propagate faster but increases query volume.

Negative caching stores the fact that a name does not exist. Happy eyeballs races IPv6 and IPv4 connections to reduce startup delay.
