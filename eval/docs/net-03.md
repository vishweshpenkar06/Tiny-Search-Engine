# HTTP Status Codes

HTTP status codes tell a client the outcome of a request. Codes in the 2xx range mean success, 4xx mean the request was invalid, and 5xx mean the server failed.

Use 400 for malformed input, 401 for missing authentication, 403 for a forbidden action, 404 for a missing resource, and 429 when a rate limit is hit.

Idempotent methods such as GET and PUT can be retried safely. POST is not idempotent unless the server supports an idempotency key.
