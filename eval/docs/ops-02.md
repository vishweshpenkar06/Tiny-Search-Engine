# Container Resource Limits

Resource limits keep one container from starving the rest of a host. CPU limits cap scheduling share, while memory limits trigger a restart when exceeded.

Set limits from measured usage rather than guesses. Leave headroom for peaks during startup and indexing.

Readiness and liveness probes should check different things: readiness gates traffic, while liveness decides whether to restart. Slow startup needs a start period.
