"""Benchmark script — must complete in < 0.5s.

The initial implementation is intentionally naive. The agent should
optimize the functions to pass the time limit.
"""

from __future__ import annotations

import time


def find_duplicates(items: list[int]) -> list[int]:
    """Find all duplicate values in a list.

    INTENTIONALLY SLOW: O(n²) nested loop.
    """
    duplicates: list[int] = []
    for i, val in enumerate(items):
        for j in range(i + 1, len(items)):
            if val == items[j] and val not in duplicates:
                duplicates.append(val)
    return sorted(duplicates)


def count_pairs_with_sum(arr: list[int], target: int) -> int:
    """Count pairs of elements that sum to `target`.

    INTENTIONALLY SLOW: O(n²) brute force.
    """
    count = 0
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            if arr[i] + arr[j] == target:
                count += 1
    return count


def matrix_multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """Multiply two matrices.

    INTENTIONALLY SLOW: naive triple loop, Python-level.
    """
    rows_a, cols_a = len(a), len(a[0])
    cols_b = len(b[0])
    result = [[0.0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    return result


def longest_common_subsequence(s1: str, s2: str) -> int:
    """Return the length of the longest common subsequence.

    INTENTIONALLY SLOW: naive recursive without memoization.
    """
    if not s1 or not s2:
        return 0
    if s1[-1] == s2[-1]:
        return 1 + longest_common_subsequence(s1[:-1], s2[:-1])
    return max(
        longest_common_subsequence(s1[:-1], s2),
        longest_common_subsequence(s1, s2[:-1]),
    )


# --------------- benchmark harness ---------------

def main() -> None:
    import random
    random.seed(0)

    data = [random.randint(0, 5000) for _ in range(10_000)]

    start = time.perf_counter()

    # 1. find_duplicates on 10k items
    find_duplicates(data[:3000])

    # 2. count_pairs_with_sum on 5k items
    count_pairs_with_sum(data[:2000], 5000)

    # 3. matrix_multiply 80×80
    size = 80
    A = [[random.random() for _ in range(size)] for _ in range(size)]
    B = [[random.random() for _ in range(size)] for _ in range(size)]
    matrix_multiply(A, B)

    # 4. LCS on two 18-char strings
    longest_common_subsequence("AGGTABCXYZWVUTSRQP", "GXTXAYZBCWVUTSRQPX")

    elapsed = time.perf_counter() - start
    print(f"elapsed: {elapsed:.3f}s")


if __name__ == "__main__":
    main()
