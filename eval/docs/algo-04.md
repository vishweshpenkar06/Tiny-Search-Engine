# Hash Tables and Collisions

A hash table maps keys to buckets with a hash function. Average lookup is O(1), but a poor hash function can degrade to O(n).

Separate chaining stores a list per bucket, while open addressing probes for the next free slot. Load factor triggers a resize to keep probes short.

Resizing rehashes every entry, so amortized cost stays constant. Use a stable hash for keys that persist across runs.
