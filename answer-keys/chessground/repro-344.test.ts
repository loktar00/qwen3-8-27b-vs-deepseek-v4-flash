// Frozen 2026-08-20 from issue #344's reproduction (position R7/6k1/8/8/5pp1/8/p4PK1/r7, black to move, white premoves).
// Primary check for the chessground live-bug task. Mirrors the repo's existing test style (tests/*.test.ts, globals).
import { defaults } from '../src/state';
import { read } from '../src/fen';
import { premove } from '../src/premove';

function stateFor(fen: string) {
  const s = defaults();
  s.pieces = read(fen);
  s.turnColor = 'black'; // black to move => white pieces are premovable
  return s;
}

describe('issue #344 — premove path check near the board edge', () => {
  const fen = 'R7/6k1/8/8/5pp1/8/p4PK1/r7';
  test('white rook premove on a8 does not throw', () => {
    expect(() => premove(stateFor(fen), 'a8')).not.toThrow();
  });
  test('white king premove on g2 does not throw', () => {
    expect(() => premove(stateFor(fen), 'g2')).not.toThrow();
  });
  test('white pawn premove on f2 does not throw', () => {
    expect(() => premove(stateFor(fen), 'f2')).not.toThrow();
  });
});
