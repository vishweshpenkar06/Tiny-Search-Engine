# Binary Search and Complexity

Binary search finds a target in a sorted array by halving the search interval each step. Its time complexity is O(log n) and it needs only O(1) extra space.

The loop must maintain an invariant: the target, if present, lies between the low and high bounds. Using low plus half the difference avoids integer overflow.

For unsorted data, sort first or use a hash table. Binary search also finds insertion points and lower bounds with a small change to the comparison.
