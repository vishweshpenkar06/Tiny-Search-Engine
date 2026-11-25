# Graph Traversal: Breadth First

Breadth first search visits nodes level by level using a queue. It finds the shortest path in an unweighted graph because it explores by distance from the start.

Mark nodes as visited when enqueuing them, not when dequeuing, to avoid duplicate work. The predecessor map reconstructs the path after the target is found.

Depth first search uses a stack and is preferable when memory is tight or when exploring a large branching structure. Both traversals are O(vertices plus edges).
