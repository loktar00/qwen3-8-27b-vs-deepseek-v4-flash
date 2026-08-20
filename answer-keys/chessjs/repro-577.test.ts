// Frozen 2026-08-20 from issue #577's reproduction. Primary check for the chess.js live-bug task.
import { describe, it, expect } from 'vitest'
import { Chess } from '../src/chess'
describe('issue #577 — pawn on edge rank move generation', () => {
  it('moves() for a white pawn placed on h8 does not throw', () => {
    const chess = new Chess()
    chess.clear()
    chess.put({ type: 'k', color: 'w' }, 'e1')
    chess.put({ type: 'k', color: 'b' }, 'e8')
    chess.put({ type: 'p', color: 'w' }, 'h8')
    expect(() => chess.moves({ square: 'h8', verbose: true })).not.toThrow()
  })
})
