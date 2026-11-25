# TLS Handshake Basics

TLS provides confidentiality and integrity for HTTP traffic. The handshake negotiates a cipher suite and authenticates the server with a certificate chain.

Session resumption removes a full round trip on later connections. TLS 1.3 reduces handshake latency by combining steps.

Certificate rotation must be automated because a single expired certificate takes a service offline. Monitor expiry dates well in advance.
