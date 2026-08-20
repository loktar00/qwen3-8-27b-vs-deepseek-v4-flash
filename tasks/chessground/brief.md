# Task: fix a reported bug in `chessground`

## Bug report (from the project's issue tracker; reporter's proposed patch removed)
**Disconnect ResizeObserver on destroy and on redraw**

## Disconnect ResizeObserver on destroy and on redraw

`bindBoard` constructs a `ResizeObserver` and observes `state.dom.elements.wrap`, but the observer is never stored or disconnected. This causes two distinct leaks:

**Leak 1 — destroy:** `api.destroy()` calls `state.dom.unbind?.()`, which only unbinds the listeners registered by `bindDocument` (it returns the unbind function; `bindBoard` does not). The `ResizeObserver` is never disconnected, so the global RO controller continues to retain the wrap element — and through it, the entire detached board subtree.

**Leak 2 — redraw:** `bindBoard` is called from inside `redrawAll`, which runs on every config change that rebuilds the DOM via `renderWrap`. Each call constructs a *new* RO observing the *new* wrap, but the *previous* RO is left observing the *previous* wrap (now detached). Within a single chessground lifetime, the observer count grows by one per full redraw. The previous RO's `onResize` callback also closes over the previous redraw's `elements`, so if it ever fires (e.g., the detached wrap is somehow resized), it operates on a partly-stale view of state.

_(Reporter's proposed patch omitted.)_

### Reproduction

#### Reproduction — heap snapshot

```html
<!doctype html>
<div id="root"></div>
<script type="module">
import { Chessground } from '@lichess-org/chessground';
window.test = () => {
  for (let i = 0; i < 100; i++) {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'width:200px;height:200px';
    document.body.appendChild(wrap);
    const cg = Chessground(wrap, { viewOnly: true });
    cg.destroy();
    wrap.remove();
  }
};
</script>
```

Run `test()` from the console, take a heap snapshot, filter for `ResizeObserver` and `cg-board`. Observed: 100 detached observers and 100 detached board subtrees retained.

## Standing instructions (identical for every run)
You are working in the repository at the current working directory. Work like a careful open-source contributor:
1. Reproduce the bug first (write a minimal failing test or script) before changing code.
2. Find the root cause; fix the cause, not the symptom. Keep the change minimal and in the project's style.
3. Add or update a regression test that fails before your fix and passes after.
4. Run the project's test suite and make it green. Do not modify or delete unrelated tests.
5. When done, summarize: root cause, the files you changed, how you verified it.
Do not ask me for permission between steps; proceed until the task is complete, then report.

Test command for this repo: `npm test`
