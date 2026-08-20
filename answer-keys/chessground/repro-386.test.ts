// Frozen 2026-08-20 from issue #386 (ResizeObserver never disconnected on destroy / leaked on every redraw).
// Upstream fix PR #387 shipped no test, so this is the primary check for the chessground hidden-reference task.
// Runs under the repo's vitest config (environment: jsdom, globals: true).
import { Chessground } from '../src/chessground';

type Ctor = typeof globalThis.ResizeObserver;
const created: Array<{ disconnected: boolean; observed: Element[] }> = [];

class FakeRO {
  entry = { disconnected: false, observed: [] as Element[] };
  constructor(_cb: ResizeObserverCallback) { created.push(this.entry); }
  observe(el: Element) { this.entry.observed.push(el); }
  unobserve() {}
  disconnect() { this.entry.disconnected = true; }
}

describe('issue #386 — ResizeObserver lifecycle', () => {
  let savedRO: Ctor | undefined;
  beforeEach(() => {
    created.length = 0;
    savedRO = (globalThis as any).ResizeObserver;
    (globalThis as any).ResizeObserver = FakeRO;
    (window as any).ResizeObserver = FakeRO;
  });
  afterEach(() => {
    (globalThis as any).ResizeObserver = savedRO;
    (window as any).ResizeObserver = savedRO;
  });

  test('destroy() disconnects every observer that was created', () => {
    const el = document.createElement('div');
    document.body.appendChild(el);
    const api = Chessground(el, {});
    expect(created.length).toBeGreaterThan(0);
    api.destroy();
    expect(created.every(o => o.disconnected)).toBe(true);
    el.remove();
  });

  test('repeated redrawAll() does not accumulate live observers', () => {
    const el = document.createElement('div');
    document.body.appendChild(el);
    const api = Chessground(el, {});
    api.redrawAll();
    api.redrawAll();
    const live = created.filter(o => !o.disconnected).length;
    expect(live).toBeLessThanOrEqual(1);
    api.destroy();
    el.remove();
  });
});
