// Frozen 2026-08-20 from issue #322's reproduction. Primary check for the chessground live-bug task.
//
// NOTE ON APPROACH: a full Chessground(el, config) instance relies on
// getBoundingClientRect() for board-bounds math, which jsdom does not
// compute (it always returns a zero rect), so a real mousedown dispatched
// on the DOM cannot be reliably translated to a board square in this test
// environment. Per the task instructions, this falls back to calling the
// exported click entry point (drag.ts `start`) directly against a minimal
// hand-built `State`, with a `dom.bounds()` stub that returns a concrete
// 800x800 rect so the position -> square math in board.getKeyAtDomPos is
// exact and deterministic (click at (50,750) -> square 'a1', which is
// empty on both the initial board and here).
import { describe, it, expect } from 'vitest'
import { start as dragStart } from '../src/drag'
import { defaults, type State } from '../src/state'
import { memo } from '../src/util'
import type * as cg from '../src/types'

describe('issue #322 — clicking an empty/opponent square always clears drawable shapes', () => {
  it('does not clear existing shapes on a left click, when the only current option that could suppress erasing (eraseOnMovablePieceClick) is set to false', () => {
    const state = defaults() as State
    state.pieces = new Map() // empty board: a1 has no piece, so this is not a "movable piece click"
    state.turnColor = 'white'
    state.selected = undefined
    state.drawable.enabled = true
    // This is the only click-erase option chessground currently exposes.
    // Per its own doc comment (src/config.ts), it only controls clicks on
    // *movable pieces*: "Clicking an empty square or immovable piece will
    // clear the drawing regardless". Setting it to false is exactly what
    // the issue reporter tried, expecting shapes to survive a click.
    state.drawable.eraseOnMovablePieceClick = false
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

    // Left mousedown on square a1 (empty square, bottom-left corner from White's POV).
    const mousedown = {
      type: 'mousedown',
      buttons: 1,
      clientX: 50,
      clientY: 750,
      isTrusted: true,
      preventDefault: () => {},
    } as unknown as cg.MouchEvent

    dragStart(state, mousedown)

    // The shape should survive: the user has no piece under the cursor and
    // has explicitly opted out of the only erase-on-click switch chessground
    // offers. Today drawClear still fires because drag.ts's condition is
    // `eraseOnMovablePieceClick || !piece || piece.color !== turnColor`,
    // which erases on ANY empty-square click regardless of the flag.
    expect(state.drawable.shapes.length).toBe(1)
  })
})
