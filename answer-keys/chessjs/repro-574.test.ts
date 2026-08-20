// Frozen 2026-08-20 from issue #574's reproduction. Primary check for the chess.js live-bug task.
import { describe, it, expect } from 'vitest'
import { Chess } from '../src/chess'

describe('issue #574 — forceEnpassantSquare ignored when no adjacent enemy pawn can capture', () => {
  it('fen({ forceEnpassantSquare: true }) reports the ep square after 1.e4 even though no black pawn is adjacent to capture it', () => {
    const chess = new Chess()
    chess.move('e4')
    expect(chess.fen({ forceEnpassantSquare: true })).toBe(
      'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
    )
  })
})
