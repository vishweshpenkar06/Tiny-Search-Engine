# TCP Congestion Control

TCP congestion control adjusts the sending rate to the capacity of the path. Slow start grows the congestion window quickly, then congestion avoidance grows it linearly.

When a loss is detected the window shrinks. Modern algorithms such as BBR estimate bandwidth and delay instead of relying only on loss.

Retransmission timeouts are computed from round trip samples. A stable estimate avoids spurious retransmits and keeps throughput high.
