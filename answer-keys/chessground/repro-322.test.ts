// Frozen 2026-08-20 from issue #322's reproduction; AMENDED 2026-08-20 (pre-verdict,
// after the first chessground #322 run).
//
// Why amended: the original version of this test hard-coded the assumption that a
// correct fix would repurpose the existing `eraseOnMovablePieceClick` flag. DSV4's
// first-run fix instead added a NEW master switch, `drawable.eraseOnClick` (default
// true), and left `eraseOnMovablePieceClick` alone — a design that fully satisfies
// what the issue actually asks for ("I would like to be able to disable the 'erase
// on click' functionality somehow"). The hard-coded assumption penalized that valid
// design. This version is DESIGN-AGNOSTIC: instead of naming a specific flag, it
// discovers every boolean field on `state.drawable` whose name contains "erase" and
// turns all of them off, so it accepts `eraseOnMovablePieceClick`, a new
// `eraseOnClick`, or any similarly named flag a model introduces.
//
// NOTE ON APPROACH for cases 1 and 2: a full Chessground(el, config) instance
// relies on getBoundingClientRect() for board-bounds math, which jsdom does not
// compute (it always returns a zero rect), so these two cases call the exported
// click entry point (drag.ts `start`) directly against a minimal hand-built
// `State`, with a `dom.bounds()` stub that returns a concrete 800x800 rect so the
// position -> square math in board.getKeyAtDomPos is exact and deterministic
// (click at (50,750) -> square 'a1', which is empty on both the initial board and
// here). Case 3 below instead goes through the full public `Chessground(el,
// config)` API and a real dispatched DOM MouseEvent — bounds turned out not to be
// a hard blocker there either: jsdom lets you override an individual element's
// getBoundingClientRect after construction, so case 3 patches the board element's
// method and clears the (already-computed) bounds memo before dispatching.
import { describe, it, expect } from 'vitest'
import { start as dragStart } from '../src/drag'
import { configure } from '../src/config'
import { Chessground } from '../src/chessground'
import { defaults, type State } from '../src/state'
import { memo } from '../src/util'
import type * as cg from '../src/types'

// Every boolean field on `drawable` whose name mentions "erase" — whatever a fix
// chooses to call it.
function eraseFlagNames(drawable: Record<string, unknown>): string[] {
  return Object.entries(drawable)
    .filter(([key, value]) => /erase/i.test(key) && typeof value === 'boolean')
    .map(([key]) => key)
}

function stubbedState(): State {
  const state = defaults() as State
  state.pieces = new Map() // empty board: a1 has no piece, so this is not a "movable piece click"
  state.turnColor = 'white'
  state.selected = undefined
  state.drawable.enabled = true
  state.drawable.shapes = [{ orig: 'e4', brush: 'green' }]
  state.dom = {
    elements: {
      board: document.createElement('div'),
      wrap: document.createElement('div'),
      container: document.createElement('div'),
    },
    bounds: memo(() => ({ left: 0, top: 0, width: 800, height: 800, right: 800, bottom: 800 }) as DOMRectReadOnly),
    redraw: () => {},
    redrawNow: () => {},
  }
  return state
}

// Left mousedown on square a1 (empty square, bottom-left corner from White's POV),
// called directly against the internal drag entry point.
function clickA1Internal(state: State): void {
  const mousedown = {
    type: 'mousedown',
    buttons: 1,
    clientX: 50,
    clientY: 750,
    isTrusted: true,
    preventDefault: () => {},
  } as unknown as cg.MouchEvent
  dragStart(state, mousedown)
}

describe('issue #322 — clicking an empty/opponent square should be able to spare drawable shapes', () => {
  it('sanity: unmodified defaults still clear shapes on an empty-square click (guards against a "fix" that just disables erase-on-click outright, unconditionally)', () => {
    const state = stubbedState()
    expect(eraseFlagNames(state.drawable as unknown as Record<string, unknown>).length).toBeGreaterThan(0)
    clickA1Internal(state)
    expect(state.drawable.shapes.length).toBe(0)
  })

  it('turning every erase-related drawable flag off (whatever it/they are named) must stop an empty-square click from clearing shapes', () => {
    const state = stubbedState()
    const flags = eraseFlagNames(state.drawable as unknown as Record<string, unknown>)
    for (const flag of flags) (state.drawable as unknown as Record<string, boolean>)[flag] = false
    clickA1Internal(state)
    expect(state.drawable.shapes.length).toBe(1)
  })

  it('same guarantee holds end-to-end: flags applied through the public Chessground(el, config)/configure() API, click dispatched as a real DOM MouseEvent on the board element', () => {
    const flags = eraseFlagNames((defaults() as State).drawable as unknown as Record<string, unknown>)
    const drawableConfig: Record<string, unknown> = {}
    for (const flag of flags) drawableConfig[flag] = false

    const el = document.createElement('div')
    document.body.appendChild(el)
    try {
      const api = Chessground(el, {
        trustAllEvents: true, // programmatically dispatched DOM events are never e.isTrusted in jsdom
        drawable: drawableConfig as unknown as never,
      } as unknown as Parameters<typeof Chessground>[1])

      // Put the board in the same state as cases 1/2: empty, with one shape on e4.
      configure(api.state, { drawable: { shapes: [{ orig: 'e4', brush: 'green' }] } } as unknown as never)
      api.state.pieces = new Map()

      // jsdom has no layout engine, so getBoundingClientRect() is always a zero
      // rect; patch the actual board element and clear the cached bounds memo so
      // click -> square math is exact.
      const board = api.state.dom.elements.board
      board.getBoundingClientRect = () =>
        ({ left: 0, top: 0, width: 800, height: 800, right: 800, bottom: 800, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect
      api.state.dom.bounds.clear()

      board.dispatchEvent(
        new MouseEvent('mousedown', { clientX: 50, clientY: 750, buttons: 1, bubbles: true, cancelable: true }),
      )

      expect(api.state.drawable.shapes.length).toBe(1)
    } finally {
      document.body.removeChild(el)
    }
  })
})
