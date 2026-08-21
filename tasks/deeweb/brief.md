# Task: CAL-7207 — Fix pinned chat ordering and add drag-and-drop reordering

*[file-path pointers and internal references given to the models are redacted here]*

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
- The read path is correct: the existing chat-list component sorts pinned channels by the stored order number
- The write path is the bug: the pin/unpin handler. Unpin filters the entry out without renumbering the rest. Pin assigns the new order from the current pinned-list length, a count, not max order plus one
- Example: pin A, B, C, D giving orders 0 to 3. Unpin A and C, leaving D at 3. The next two pins get orders 1 and 2, so both sort above D even though D was pinned first
- The same missing renumber exists in the handler that runs when a channel is deleted or the user leaves it
- Smaller related issue: the new-member-joined handler can insert an unpinned channel above the whole pinned block when the last pinned channel is not in the loaded list yet
- Fix direction: renumber the whole array densely (order equals index) on every write. The save request replaces the full pinned-list array, so a save is a single mutation
- For drag-and-drop: a drag-and-drop library was already installed, with an existing working sortable pattern elsewhere in the app to copy. Use a drag handle so rows stay clickable to open the chat
- Edit mode keeps the avatar. On a pinned row the avatar costs no height at all, because the 44px handle touch target already sets the row height. The sidebar minimum width is 320px and the name still gets about 154px next to the checkbox, avatar and handle
- Keeping avatars matters because names repeat in the real list. There are two Bethany University rows and two Agents rows on the test account
- The pinned heading only renders when there is at least one pin, so the first pin still has to come from the existing right-click Pin Channel action. Do not remove it
