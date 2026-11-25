# Dynamic Programming Patterns

Dynamic programming replaces repeated recursive work with a table of subproblem results. It applies when a problem has overlapping subproblems and optimal substructure.

A bottom up tabulation avoids recursion depth limits. A top down memoization is easier to write when only some states are reachable.

Classic examples include edit distance, knapsack, and matrix chain order. State the recurrence before writing code so the table dimensions are obvious.
