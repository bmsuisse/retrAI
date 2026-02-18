"""Tests for utils.py — these are correct, the source code has bugs."""

from __future__ import annotations

import pytest

from utils import Stack, binary_search, caeser_cipher, fibonacci, flatten, merge_sorted


# ---------- fibonacci ----------

@pytest.mark.parametrize(
    "n, expected",
    [(0, 0), (1, 1), (2, 1), (3, 2), (5, 5), (10, 55), (20, 6765)],
)
def test_fibonacci(n: int, expected: int) -> None:
    assert fibonacci(n) == expected


def test_fibonacci_negative() -> None:
    assert fibonacci(-1) == 0


# ---------- flatten ----------

def test_flatten_simple() -> None:
    assert flatten([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]


def test_flatten_empty() -> None:
    assert flatten([]) == []


def test_flatten_already_flat() -> None:
    assert flatten([1, 2, 3]) == [1, 2, 3]


def test_flatten_deeply_nested() -> None:
    assert flatten([[[[[1]]]]]) == [1]


# ---------- merge_sorted ----------

def test_merge_sorted_basic() -> None:
    assert merge_sorted([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]


def test_merge_sorted_empty() -> None:
    assert merge_sorted([], [1, 2]) == [1, 2]
    assert merge_sorted([1, 2], []) == [1, 2]


def test_merge_sorted_duplicates() -> None:
    assert merge_sorted([1, 2, 3], [2, 3, 4]) == [1, 2, 2, 3, 3, 4]


# ---------- caeser_cipher ----------

def test_caeser_cipher_encrypt() -> None:
    assert caeser_cipher("abc", 3) == "def"


def test_caeser_cipher_decrypt() -> None:
    assert caeser_cipher("def", -3) == "abc"


def test_caeser_cipher_wrap() -> None:
    assert caeser_cipher("xyz", 3) == "abc"


def test_caeser_cipher_preserves_non_alpha() -> None:
    assert caeser_cipher("Hello, World!", 13) == "Uryyb, Jbeyq!"


# ---------- Stack ----------

def test_stack_push_pop() -> None:
    s = Stack()
    s.push(1)
    s.push(2)
    assert s.pop() == 2
    assert s.pop() == 1


def test_stack_peek() -> None:
    s = Stack()
    s.push(42)
    assert s.peek() == 42
    assert s.size == 1


def test_stack_empty() -> None:
    s = Stack()
    assert s.is_empty
    with pytest.raises(IndexError):
        s.pop()


# ---------- binary_search ----------

def test_binary_search_found() -> None:
    arr = [1, 3, 5, 7, 9, 11, 13]
    assert binary_search(arr, 7) == 3


def test_binary_search_not_found() -> None:
    arr = [1, 3, 5, 7, 9]
    assert binary_search(arr, 4) == -1


def test_binary_search_first_element() -> None:
    arr = [10, 20, 30, 40, 50]
    assert binary_search(arr, 10) == 0


def test_binary_search_last_element() -> None:
    arr = [10, 20, 30, 40, 50]
    assert binary_search(arr, 50) == 4


def test_binary_search_empty() -> None:
    assert binary_search([], 5) == -1


def test_binary_search_single() -> None:
    assert binary_search([42], 42) == 0
    assert binary_search([42], 7) == -1
