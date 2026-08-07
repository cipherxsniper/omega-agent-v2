def fibonacci_memo(n):
    """Compute the nth Fibonacci number using memoization."""
    memo = {}

    def fib(k):
        if k in memo:
            return memo[k]
        if k <= 1:
            return k
        memo[k] = fib(k - 1) + fib(k - 2)
        return memo[k]

    return fib(n)


if __name__ == "__main__":
    print(fibonacci_memo(30))