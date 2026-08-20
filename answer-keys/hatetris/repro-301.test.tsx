// Frozen 2026-08-20 as the hatetris #301 P1 check (see SCORING.md change log).
//
// Replaces the upstream PR's own test file for P1. The upstream fix-pr-310.diff bundles the
// actual behavioral fix (hand control back to the player when a replay runs out of moves but
// the game isn't over) together with an UNRELATED refactor that adds `data-testid` to every
// control button and renames the existing one from 'down' to 'down-button'. Since P1 only ever
// patches test files (never the paired source change), that renamed testid never exists in a
// worktree that didn't happen to also do the same refactor -- so the upstream tests fail on any
// correct fix that doesn't replicate an incidental naming choice, not on a real regression.
// Confirmed on two independent DSV4 fixes: both hand control back correctly (this test passes
// against both worktrees unmodified), but both fail the upstream test file purely on the
// testid mismatch -- and because that file has no afterEach(cleanup) and node's test runner +
// global-jsdom share ONE document for the whole file, an early throw (before a test's own
// game.unmount()) leaks DOM into later tests and can make even unrelated tests fail too.
//
// This test avoids all of that: it only touches the well grid's cell testids (well__cell--live),
// which are unchanged across the base commit, the upstream fix, and both DSV4 fixes, and it
// unmounts unconditionally (try/finally) so it can never leak state into anything run after it,
// no matter how it exits. Self-contained: does not import anything from Game.test.tsx.
//
// Validated: fails on the base commit (mode stays REPLAYING forever, the Down keypress is
// dropped -- log line "Ignoring event D because mode is REPLAYING", live-cell coordinates
// unchanged), passes with the upstream's full fix applied, and passes on both DSV4 worktrees.
import assert from 'node:assert/strict'
import { describe, it, beforeEach, afterEach } from 'node:test'

import userEvent from '@testing-library/user-event'
import { render, screen } from '@testing-library/react'
import * as React from 'react'
import * as sinon from 'sinon'
import Game from '../../../src/components/Game/Game.tsx'
import type { GameProps } from '../../../src/components/Game/Game.tsx'
import hatetrisRotationSystem from '../../../src/rotation-systems/hatetris-rotation-system.ts'

const replayTimeout = 0
const copyTimeout = 100

describe('issue #301 -- replay handoff (design-agnostic)', () => {
  const renderGame = (props: Partial<GameProps> = {}) => render(
    <Game
      bar={4}
      copyTimeout={copyTimeout}
      replayTimeout={replayTimeout}
      rotationSystem={hatetrisRotationSystem}
      wellDepth={20}
      wellWidth={10}
      {...props}
    />
  )

  let user: ReturnType<typeof userEvent.setup>
  let mounted: ReturnType<typeof renderGame> | undefined

  beforeEach(() => {
    user = userEvent.setup()
    mounted = undefined
  })

  // Unconditional cleanup: runs even if the test body throws, so this file can never leave a
  // mounted Game behind for anything that runs after it in the same shared jsdom document.
  afterEach(() => {
    if (mounted) {
      mounted.unmount()
      mounted = undefined
    }
  })

  const advanceReplaySteps = async (n: number) => {
    for (let i = 0; i < n; i++) {
      await new Promise(resolve => setTimeout(resolve, replayTimeout))
    }
  }

  // Fingerprint of the live (falling) piece's cells by grid coordinate. Deliberately does NOT
  // depend on any specific testid naming for the control buttons -- only on the well grid's
  // cell testids, which are unchanged across base/upstream-fix/both DSV4 diffs.
  const getLiveCellCoords = () => {
    const cells = new Set<string>()
    const rows = Array.from(document.querySelectorAll('tbody tr'))
    rows.forEach((tr, y) => {
      Array.from(tr.children).forEach((td, x) => {
        const testId = td.getAttribute('data-testid') ?? ''
        if (testId.split(' ').includes('well__cell--live')) {
          cells.add(`${y},${x}`)
        }
      })
    })
    return cells
  }

  it('lets the player move the piece after a too-short replay ends, regardless of which UI element signals control is back', async () => {
    mounted = renderGame()

    // Replay a single Down move, then keep advancing timeouts past the end of
    // the supplied replay -- the game is nowhere near over after one move.
    const prompt = sinon.stub(window, 'prompt')
    prompt.returns('D')
    await user.click(screen.getByTestId('replay-button'))
    assert.deepEqual(prompt.getCalls().map(call => call.args), [
      ['Paste replay string...']
    ])
    prompt.restore()

    await advanceReplaySteps(3)

    // Snapshot the falling piece's position, then press Down and snapshot again.
    // If the player has genuinely been handed control back, the piece moves and
    // the live-cell coordinates change. If the game is still stuck in replay
    // mode (or otherwise not accepting input), the board is unchanged.
    const before = getLiveCellCoords()
    assert.ok(before.size > 0, 'expected a live piece on the board after the replay')

    await user.keyboard('{Down}')

    const after = getLiveCellCoords()
    assert.notDeepEqual(
      Array.from(after).sort(),
      Array.from(before).sort(),
      'expected the Down keypress after the replay ended to move the piece (player has control back)'
    )
  })
})
