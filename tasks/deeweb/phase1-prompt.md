# deeweb CAL-7207 — Phase 1 (design) prompt — paste VERBATIM to each model, in its own worktree

Setup (Jason's call 2026-08-20: work in D:\devNewman\called-deeweb-web-3, SEQUENTIALLY):
  DSV4 first:  branch ab/dsv4-cal7207 @ 1f680c659 (created by orchestrator); open OMP there with
               pod-dsv4/deepseek-v4-flash-0731 --no-extensions --no-skills --no-rules; Phase 1 then Phase 2; commit all.
  Qwen second: git checkout -b ab/qwen-cal7207 1f680c659 ; open OMP with pod-qwen/qwen3.8-27b-bf16 (same flags);
               Phase 1 then Phase 2; commit all. Restore afterwards: git checkout <branch in web-3-original-branch.txt>.
  (web-1 holds the Claude PR branch bug/CAL-7207-pinned-chat-ordering — never touch it.)
Paste the prompt below verbatim; same follow-ups to both models in the same order. Do NOT paste the prototype link —
Phase 1 is the models' own design.

---- PROMPT (Phase 1) ----

I need a UX design for a change in this app's chat sidebar. Read the ticket below, look at the existing chat
list code under apps/called-chat/src/views/Community/Chat/ContactList/ (and ChannelMenu) to understand the
current structure and styling conventions, and then produce THREE distinct static HTML mockups of the proposed
"edit mode" for pinned chats: files mock-A.html, mock-B.html, mock-C.html at the repo root, each self-contained
(inline CSS, no build step), each showing the sidebar at 320px width in both the normal state and the edit state,
using the real visual language of this app (fonts, spacing, colors as found in the SCSS). Each mock should take a
genuinely different approach to where the Edit control lives and how rows change in edit mode. Do not modify any
application code in this phase. When done, summarize the three directions in one paragraph each.

Ticket:

## Story
Pinned chats in the chat list don't hold their order. The backend stores an order number for every pinned channel and the frontend sorts by that number, so the display side is working correctly. The issue is on write, pinning and unpinning never renumber the stored orders. Unpinning leaves gaps in the sequence, and pinning assigns the new order based on the array length, so numbers collide and new pins can land above older ones.
Users also have no way to rearrange their pinned chats. Rather than leaving drag handles visible all the time, which makes the list noisy, pinned editing goes behind an explicit edit mode. An Edit button sits in the empty right half of the PINNED heading. Turning it on puts a checkbox on every row so you can pin and unpin in bulk, shows a drag handle on the pinned rows, and gives you Save and Cancel. Turning it off puts the list back to normal.

## Acceptance Criteria
- Pinned chats always render in the backend-stored order, stable across refetches
- Pinning a new chat adds it to the end of the pinned section, never above older pins
- Unpinning (including channel delete or leave) keeps the remaining pins in their existing order
- Drag handles are not visible until the user turns on Edit
- In edit mode the user can check and uncheck chats to pin them, and drag pinned chats to reorder
- Save persists both the new pin set and the new order in one request, and the order survives a reload
- Cancel leaves the pinned chats exactly as they were
- Outside edit mode, rows still open the chat on click
- The drag handle is reachable and operable by keyboard

## Notes
- Edit mode keeps the avatar. Names repeat in the real list (two "Bethany University" rows, two "Agents" rows), so rows must stay tellable apart.
- The sidebar minimum width is 320px.
- The pinned heading only renders when there is at least one pin.

---- END PROMPT ----

Blind pick: after both models finish, I (orchestrator) copy the six mocks to a neutral folder as A1..A3 / B1..B3 with
the model mapping hidden, Jason opens them in a browser and picks one per set; mapping revealed after. Recorded as
subjective/illustrative per SCORING §2C.

Phase 2 prompt = D:\dev\ab-tasks\_briefs\deeweb\brief.md (the full ticket incl. Tasks + Notes, the agreed direction),
run in the SAME worktree after resetting any mock files (git clean -fd), scored by the 9-criteria checklist.
