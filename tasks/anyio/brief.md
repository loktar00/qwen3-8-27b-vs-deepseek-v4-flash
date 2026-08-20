# Task: fix a reported bug in `anyio`

## Bug report (verbatim from the project's issue tracker)
**CapacityLimiter can over-grant tokens (`borrowed_tokens > total_tokens`, `available_tokens` goes negative)**

### Things to check first

- [x] I have searched the existing issues and didn't find my bug already reported there

- [x] I have checked that my bug is still present in the latest release


### AnyIO version

4.13.0

### Python version

3.12

### What happened?

On the asyncio backend, a non-blocking acquire can succeed *while the just-freed token is already reserved for a woken waiter*, leaving the limiter with more borrowers than it has tokens. The state becomes:

```
borrowed_tokens  = 2
total_tokens     = 1
available_tokens = -1      # negative
borrowers        = ('B', 'X')
```

Two tasks then hold a single-token limiter concurrently — the exact condition the limiter exists to prevent — and `available_tokens` is negative.

This violates the documented contract of `acquire_nowait` / `acquire_on_behalf_of_nowait`:

> :raises ~anyio.WouldBlock: if there are no tokens available for borrowing

In the window below there is no token available (the freed one is earmarked for the woken waiter), yet the nowait acquire succeeds instead of raising `WouldBlock`.

### How can we reproduce the bug?

Just anyio, no test framework: `python repro.py` prints the corrupt state and raises `AssertionError`:

```python
import anyio
from anyio import CapacityLimiter, WouldBlock

async def main():
    lim = CapacityLimiter(1)                       # capacity: exactly ONE token
    lim.acquire_on_behalf_of_nowait("A")           # A borrows the only token

    async with anyio.create_task_group() as tg:
        async def b():
            await lim.acquire_on_behalf_of("B")    # B waits for the token
        tg.start_soon(b)

        while lim.statistics().tasks_waiting != 1:  # wait until B is parked
            await anyio.sleep(0)

        lim.release_on_behalf_of("A")              # frees the token, notifies B
        # B has been notified but has NOT resumed yet, so it is not in
        # _borrowers and the wait queue is now empty. A non-blocking acquire
        # in this window slips through:
        try:
            lim.acquire_on_behalf_of_nowait("X")  # expected: WouldBlock
            print("X acquired without waiting (should have raised WouldBlock)")
        except WouldBlock:
            print("X correctly blocked")
        # leaving the task group lets B resume and add itself to _borrowers

    print(f"borrowed_tokens  = {lim.borrowed_tokens}  (total_tokens = {lim.total_tokens})")
    print(f"available_tokens = {lim.available_tokens}")
    print(f"borrowers        = {lim.statistics().borrowers}")
    assert lim.borrowed_tokens <= lim.total_tokens, "borrowed_tokens > total_tokens"

anyio.run(main)
```

Output:

```
X acquired without waiting (should have raised WouldBlock)
borrowed_tokens  = 2  (total_tokens = 1)
available_tokens = -1
borrowers        = ('B', 'X')
AssertionError: borrowed_tokens > total_tokens
```
### Cause

In `anyio/_backends/_asyncio.py`:

- `release_on_behalf_of` removes the borrower then calls `_notify_next_waiter()`, which **pops** the next waiter out of `_wait_queue` and does `event.set()`.
- The woken waiter, in `acquire_on_behalf_of`, only adds itself to `_borrowers` **after** `await event.wait()` returns:

  ```python
  await event.wait()
  ...
  self._borrowers.add(borrower)   # runs only once the waiter resumes
  ```

- Between the `event.set()` and the waiter resuming, `_wait_queue` is empty and the waiter is not yet in `_borrowers`. So the nowait guard

  ```python
  if self._wait_queue or len(self._borrowers) >= self._total_tokens:
      raise WouldBlock
  ```

  evaluates to `False` (empty queue, `0 < 1`) and admits a second borrower for the one token.

### Why `Semaphore` is not affected

The sibling `Semaphore` is immune under the identical scenario, a nowait acquire issued in the same window correctly raises `WouldBlock`, because its `release()` hands the freed slot to the woken waiter rather than leaving it generally available. `CapacityLimiter` is the one primitive whose freed-but-reserved token is briefly visible as "available" to a synchronous acquirer.

A fix would close that window, e.g. by reserving the token for the woken waiter at notify time (add the borrower to `_borrowers` when `_notify_next_waiter` sets its event, rather than after it resumes), mirroring the Semaphore/Lock hand-off. The nowait guard would then correctly see no free token.

## Standing instructions (identical for every run)
You are working in the repository at the current working directory. Work like a careful open-source contributor:
1. Reproduce the bug first (write a minimal failing test or script) before changing code.
2. Find the root cause; fix the cause, not the symptom. Keep the change minimal and in the project's style.
3. Add or update a regression test that fails before your fix and passes after.
4. Run the project's test suite and make it green. Do not modify or delete unrelated tests.
5. When done, summarize: root cause, the files you changed, how you verified it.
Do not ask me for permission between steps; proceed until the task is complete, then report.

Test command for this repo: `.venv/Scripts/python -m pytest tests/test_synchronization.py -q`
