# Task: CAL-7207 — Fix pinned chat ordering and add drag-and-drop reordering

(Brief = the Notion ticket, verbatim. Repo: called-deeweb at develop@1f680c659. Same text Claude received.)

## Story
Pinned chats in the chat list don't hold their order. The backend stores an order number for every pinned channel and the frontend sorts by that number, so the display side is working correctly. The issue is on write, pinning and unpinning never renumber the stored orders. Unpinning leaves gaps in the sequence, and pinning assigns the new order based on the array length, so numbers collide and new pins can land above older ones.
Users also have no way to rearrange their pinned chats. Rather than leaving drag handles visible all the time, which makes the list noisy, pinned editing goes behind an explicit edit mode. An Edit button sits in the empty right half of the PINNED heading. Turning it on puts a checkbox on every row so you can pin and unpin in bulk, shows a drag handle on the pinned rows, and gives you Save and Cancel. Turning it off puts the list back to normal.

## Tasks
- Renumber pinnedChannels densely (order = index) on every write: pin, unpin, and removeChannelFromPinned
- Fix the onUserJoined insert so an unpinned channel can never land above the pinned block
- Add an Edit / Done button to the right side of the PINNED heading
- Build the edit-mode row: checkbox, avatar, name, drag handle. Avatars stay so near-identical names stay tellable apart
- Check and uncheck to pin and unpin, with the row moving between PINNED and ALL CHATS as feedback
- Drag to reorder the pinned rows, with a 44px handle so it is a real touch target
- Save writes the whole renumbered array in one request, Cancel throws the draft away
- Remove the always-visible drag handles
- Keyboard reorder and screen reader announcements on the handle
- Unit tests for the ordering helpers, the pin and unpin writes, and the edit-mode save and cancel

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
- The read path is correct: ContactList/index.tsx sorts pinned channels by the stored order number
- The write path is the bug: handlePinChannel in ChannelMenu.tsx. Unpin filters the entry out without renumbering the rest. Pin assigns the new order from pinnedChannels.length, a count, not max order plus one
- Example: pin A, B, C, D giving orders 0 to 3. Unpin A and C, leaving D at 3. The next two pins get orders 1 and 2, so both sort above D even though D was pinned first
- The same missing renumber exists in removeChannelFromPinned in ContactList/index.tsx, which runs when a channel is deleted or the user leaves it
- Smaller related issue: the onUserJoined handler in ContactList/index.tsx can insert an unpinned channel above the whole pinned block when the last pinned channel is not in the loaded list yet
- Fix direction: renumber the whole array densely (order equals index) on every write. PATCH /v1/account/settings replaces the full pinnedChannels array, so a save is a single mutation
- For drag-and-drop: @dnd-kit is already installed. The Pathway board has a working sortable pattern to copy (usePhaseReordering.ts, PathwayDragDropContext.tsx). Use a drag handle so rows stay clickable to open the chat
- Edit mode keeps the avatar. On a pinned row the avatar costs no height at all, because the 44px handle touch target already sets the row height. The sidebar minimum width is 320px and the name still gets about 154px next to the checkbox, avatar and handle
- Keeping avatars matters because names repeat in the real list. There are two Bethany University rows and two Agents rows on the test account
- The pinned heading only renders when there is at least one pin, so the first pin still has to come from the existing right-click Pin Channel action. Do not remove it

## Suggested scripted follow-ups (Jason drives; use or ignore)
T2: "Fix the ordering bug first, with tests, before any UI work."
T3: "Now the edit mode UX."
T4: "Save must be one request; the handle must be keyboard-operable and 44px; drag handles only in edit mode."
T5: "Run the suite and make it green."
T6: "Edit mode must close automatically when a search starts (search hides the pinned section)."

## Judge against (from the shipped PR #1866, NOT shown to the models)
bulk pin/unpin · drag reorder · Save persists across reload · Cancel discards · rows still open chat outside edit · existing suite green · diff size vs +1458/-126 (23 files)
