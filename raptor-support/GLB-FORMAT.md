# GLB Archive Format — Raptor: Call of the Shadows

Reference/answer-key document. Not shown to the models being graded — written for
a human/automated scorer to check a JS port against. Every structural claim is
cited `file:line` against the actual GPL source. All paths are relative to
`D:\dev\ab-tasks\raptor\` unless a full path is given. Line numbers were read
directly from the files at the time this document was written; if the source is
edited later, re-verify.

Primary sources:
- `GFX/GLBAPI.C` — the GLB reader/writer implementation (all format logic)
- `GFX/GLBAPI.H` — public API + on-disk struct declarations
- `GFX/types.h` — base type sizes (`BYTE`, `WORD`, `DWORD`, `INT`, `CHAR`)
- `SOURCE/RAP.C` — game-side usage (open, init, palette/sprite bootstrap)
- `SOURCE/GETGLB.C` — trivial extraction utility (`GLB_GetItem`+`GLB_SaveFile`)
- `SOURCE/HELP.C` — example of handle arithmetic / label ranges
- `SOURCE/FILE0000.INC`, `SOURCE/FILE0001.INC` — **generated** header files that
  give the ground-truth handle value for every named item in FILE0000.GLB and
  FILE0001.GLB. These are gold for verifying a port's lookup/decoding against
  real data.
- `GFX/GFXAPI.C`, `GFX/GFXAPI.H`, `GFX/GFXAPI_A.ASM` — image/sprite/palette
  consumers (how the raw bytes of a GLB item get interpreted once extracted)

Build target facts that matter for struct sizes/byte order (see §6): the game
is compiled 32-bit flat-model DOS (Watcom C, DOS extender/DPMI), confirmed by
`GFX/GFXAPI_A.ASM:16` (`.MODEL FLAT, C`) and `GFX/EXITAPI.H:27` (`#ifdef
__386__`) plus pervasive `int386()` DPMI calls in `GFX/GFXAPI.C`. So on this
build `INT`/`DWORD` are **4 bytes**, not the 16-bit DOS default. All of the
struct sizes below assume that build.

Base type sizes (`GFX/types.h:21-29`):
| type | size |
|---|---|
| `BYTE` | 1 byte, `unsigned char` |
| `WORD` | 2 bytes, `unsigned short` |
| `DWORD` | 4 bytes, `unsigned int` (NOT `unsigned long`; matters only for the reader's own C code, not for a JS port) |
| `CHAR` | 1 byte, `char` |
| `INT` | 4 bytes, `int`, in this 32-bit build |

Byte order: x86 native, so **little-endian** throughout (header fields, item
table fields, and the `GFX_PIC`/`GFX_SPRITE` image headers described in §5).
Nothing in the code ever byte-swaps; this is asserted from the target platform,
not from an explicit statement in the source.

---

## 1. Overall archive structure

A `.GLB` file has exactly two regions, back to back, with **no magic
signature anywhere**:

```
[0]                     KEYFILE   "pseudo-header" record (28 bytes, encrypted on disk)
[28]                    KEYFILE   directory entry 0       (28 bytes, encrypted on disk)
[28 + 28]               KEYFILE   directory entry 1
...
[28 * N]                KEYFILE   directory entry N-1
[variable, see below]   item payload bytes, at whatever absolute offsets
                        the directory entries specify (not necessarily
                        contiguous with, or immediately following, the
                        directory)
```

- The `KEYFILE` struct (`GFX/GLBAPI.H:25-31`):
  ```c
  typedef struct
  {
     DWORD   opt;           // option (encode on/off)
     DWORD   offset;        // offset into file
     DWORD   filesize;      // filesize
     CHAR    name[16];      // text name ( end with null )
  } KEYFILE;
  ```
  Field order/sizes: `opt` (4 bytes) → `offset` (4 bytes) → `filesize` (4
  bytes) → `name` (16 raw bytes). Total **28 bytes**, no padding (all
  members already 4-byte-aligned, struct size is a multiple of 4).

- **No magic bytes / signature are ever checked.** `GLB_NumItems()`
  (`GFX/GLBAPI.C:255-280`) opens the file, seeks to offset 0
  (`GFX/GLBAPI.C:269`), reads exactly `sizeof(KEYFILE)` = 28 bytes into a
  local `KEYFILE key` (`GFX/GLBAPI.C:270`), decrypts it (see §3), and
  returns `key.offset` as-is, reinterpreted as the item count
  (`GFX/GLBAPI.C:279`, `return ( ( int ) key.offset );`). There is **no
  check** that `key.opt`, `key.filesize`, or `key.name` hold any particular
  value — a "valid" GLB file is defined purely operationally: byte 0 decrypts
  to something whose `offset` field is a plausible item count, and nothing
  more. A corrupt/foreign file simply produces a garbage item count (see §6
  for what happens next).

- **The very first 28-byte record is not a directory entry** — it is a
  disguised item-count field. Its `offset` sub-field is repurposed to hold
  the total number of *real* entries that follow (`N` above); its `opt`,
  `filesize`, and `name` sub-fields are read and decrypted along with it but
  are never consulted for anything by the loader. Do not treat record 0 as
  `item[0]`.

- Item payload bytes live wherever `entry.offset` says, as an **absolute
  byte offset from the start of the file** (`GFX/GLBAPI.C:428`,
  `lseek( handle, ii->offset, SEEK_SET );`). Nothing in the code assumes the
  data region starts immediately after the last directory entry, though in
  practice the tool that built the archive presumably laid it out that way.
  A reader must not assume contiguity — always seek to `offset`.

- There is no end-of-file marker, no total-file-size field, no checksum over
  the whole file. Reading past the declared item count is bounded only by
  `filedesc[filenum].items` in memory (see §2); nothing in the on-disk
  format itself bounds the directory.

---

## 2. Entry / directory table

- **Location**: directory entries start immediately at file offset
  `sizeof(KEYFILE)` = **28** (i.e., right after the pseudo-header record) and
  run for exactly `N` consecutive 28-byte `KEYFILE` records, where `N` is the
  item count extracted from the pseudo-header in §1. This is set up in
  `GLB_LoadIDT()`: `lseek( handle, sizeof( KEYFILE ), SEEK_SET );`
  (`GFX/GLBAPI.C:300`), then a loop over `fd->items` entries
  (`GFX/GLBAPI.C:301-322`).

- **Fixed vs. computed**: the *start* of the table (byte 28) is fixed; the
  *end* is computed as `28 + N*28`, where `N` comes from the pseudo-header,
  not from any fixed constant in the format. Different GLB files have
  different `N` (compare `SOURCE/FILE0000.INC`'s highest item, `//ITEM:097`
  plus a few label markers ⇒ ~0xE5=229 records for FILE0000.GLB, vs.
  `SOURCE/FILE0001.INC` which runs much longer).

- **Read strategy**: the loader does not read the whole table in one `read()`
  call. It reads in batches of up to 10 `KEYFILE` records at a time into a
  stack buffer `KEYFILE key[10]` (`GFX/GLBAPI.C:294`, loop at
  `GFX/GLBAPI.C:301-322`, batch size clamp `GFX/GLBAPI.C:303-305` via
  `ASIZE(key)` = 10). This is purely a reader implementation detail — a
  reimplementation may read the whole table in one shot; the on-disk bytes
  are identical either way. **Important**: each 28-byte record is decrypted
  **independently** (see §3) — the batching does not change the on-disk
  format or the decryption keystream boundaries, because
  `GLB_DeCrypt(serial, (BYTE*)&key[n], sizeof(KEYFILE))` (`GFX/GLBAPI.C:311`)
  is called once per record with its own fresh keystream, inside the `n`
  loop, regardless of how many records were physically read together.

- **Per-entry fields actually used at runtime**, copied into an in-memory
  `ITEMINFO` (`GFX/GLBAPI.C:47-55`) by `GLB_LoadIDT()`
  (`GFX/GLBAPI.C:308-320`):
  | on-disk `KEYFILE` field | meaning | copied to |
  |---|---|---|
  | `opt` | `GLB_NORMAL`(0) or `GLB_ENCODED`(1) — is this item's *payload* additionally cipher-encoded (`GFX/GLBAPI.H:43-44`) | if `opt == GLB_ENCODED`, sets `ITF_ENCODED` bit (`0x40000000`) in the in-memory `ii->flags` (`GFX/GLBAPI.C:313-314`) |
  | `offset` | absolute byte offset of the item's payload in the file | `ii->offset` (`GFX/GLBAPI.C:317`) |
  | `filesize` | payload length in bytes | `ii->size` (`GFX/GLBAPI.C:316`) |
  | `name` | 16-byte ASCII item name, used for name-based lookup | `memcpy`'d verbatim, all 16 bytes, into `ii->name[16]` (`GFX/GLBAPI.C:318`) — **not** guaranteed to be null-terminated on disk (see §6) |

  There is **no on-disk "type" field** distinguishing text/picture/sound/etc.
  — the directory entry only carries offset+size+opt+name. Whatever the
  payload actually *is* (palette, image, text, music) is determined entirely
  by (a) which named/numbered slot the game asks for (the `.INC` files
  document this by convention/suffix: `_TXT`, `_PIC`, `_DAT`, `_FNT`, `_MUS`,
  `_FX`) and (b) for images specifically, a small header embedded at the
  *start of the payload itself* (see §5). A directory entry with
  `filesize == 0` is a "label" — a pure bookmark/marker with no payload at
  all (see §4's `GLB_IsLabel`, and `SOURCE/FILE0000.INC:18`
  `STARTHELP`/`SOURCE/FILE0000.INC:60` `ENDHELP` as examples, commented
  `//LABEL:` instead of `//ITEM:NNN` in the generated `.INC` files).

- **Item ordering / indexing**: item index (`itemnum`, used everywhere as
  the second half of a handle, see §4) is simply the entry's **0-based
  position in the directory table**, in the order the 28-byte records
  appear on disk — there is no separate index field on disk. Entry 0 of the
  real table (file offset 28) is item index 0, entry 1 (file offset 56) is
  item index 1, etc. This is implicit in the `for (j = 0; j < fd->items; )`
  / `ii++` walk in `GLB_LoadIDT()` (`GFX/GLBAPI.C:301-322`) — `ii` starts at
  `fd->item[0]` and is simply incremented once per record read, in file
  order.

---

## 3. Encryption / obfuscation

**There is real, deliberate, application-level obfuscation, applied at two
independent layers.** It is a byte-wise additive stream cipher (not XOR, not
a real cryptographic cipher, no compression, no CRC/checksum of any kind
anywhere in the format).

### 3a. The cipher itself

Defined in `GFX/GLBAPI.C:86-135`. Key type `CHAR *key`, buffer `BYTE
*buffer`, `size_t length`.

Encrypt (`GLB_EnCrypt`, `GFX/GLBAPI.C:86-107`):
```c
klen = strlen( key );
kidx = SEED % klen;                 // SEED == 0x0019 == 25  (GFX/GLBAPI.H:41)
prev_byte = key[ kidx ];
while ( length-- )
{
   prev_byte = ( *buffer + key[ kidx ] + prev_byte ) % 256;
   *buffer++ = prev_byte;
   if ( ++kidx >= klen ) kidx = 0;
}
```
i.e. `ciphertext[i] = (plaintext[i] + key[(SEED%klen + i) % klen] + ciphertext[i-1]) mod 256`,
with `ciphertext[-1]` initialized to `key[SEED % klen]`.

Decrypt (`GLB_DeCrypt`, `GFX/GLBAPI.C:112-135`), the exact inverse:
```c
klen = strlen( key );
kidx = SEED % klen;
prev_byte = key[ kidx ];
while ( length-- )
{
   dchr = ( *buffer - key[ kidx ] - prev_byte ) % 256;
   prev_byte = *buffer;              // ciphertext byte, read BEFORE overwrite
   *buffer++ = dchr;
   if ( ++kidx >= klen ) kidx = 0;
}
```
i.e. `plaintext[i] = (ciphertext[i] - key[(SEED%klen + i) % klen] - ciphertext[i-1]) mod 256`.

Notes for a JS port:
- This is a **running/chained** cipher (each byte's encoding depends on the
  previous byte's *ciphertext* value, plus a repeating key byte) — it is
  **not** a simple repeating-XOR. Get the "previous byte" feedback exactly
  right (ciphertext-before-overwrite on decrypt) or every byte after the
  first will decode wrong.
- `dchr` is a signed `CHAR` in the C source (`GFX/GLBAPI.C:122`) and the
  `%` there is C's truncating remainder on a value that can be negative;
  since the result is immediately stored back into an unsigned `BYTE`
  buffer, the practical effect is equivalent to `((a - b - c) & 0xFF)` /
  JS's `((a - b - c) % 256 + 256) % 256`. Use unsigned mod-256 arithmetic in
  the port and you'll match the observable behavior.
- `kidx` starts at `SEED % klen` on **every call** to `GLB_EnCrypt`/
  `GLB_DeCrypt` — the keystream always restarts from the same key-index for
  the start of whatever buffer you hand it. It does not carry state between
  calls.

### 3b. Where the cipher is applied inside the GLB format

Both application sites are guarded by `#ifdef _SCOTTGAME`, and
`_SCOTTGAME` is unconditionally `#define`'d near the top of the file
(`GFX/GLBAPI.C:35`), so **both are always active** in this build — there is
no "plaintext GLB" code path compiled in.

1. **The entire directory (pseudo-header + every entry) is always
   encrypted on disk**, unconditionally, using the fixed literal key
   `"32768GLB"` (`GFX/GLBAPI.C:37`, `PRIVATE CHAR *serial = "32768GLB";`),
   8 characters, so `klen = 8` and `kidx` starts at `SEED % 8 = 25 % 8 = 1`
   (0-based) — i.e. the keystream index starts on `'2'` (the second
   character of `"32768GLB"`).
   - Applied to the pseudo-header record in `GLB_NumItems()`:
     `GLB_DeCrypt( serial, ( BYTE * )&key, sizeof( KEYFILE ) );`
     (`GFX/GLBAPI.C:276`).
   - Applied to each of the `N` real directory entries individually in
     `GLB_LoadIDT()`: `GLB_DeCrypt( serial, ( BYTE * ) &key[ n ], sizeof(
     KEYFILE ) );` (`GFX/GLBAPI.C:311`) — called once per 28-byte record,
     each with a fresh 1-based keystream (see §2's note on batching).
   - **This directory-level decryption is unconditional** — it does not
     depend on the `opt` field (which hasn't even been decrypted yet at
     that point). Every `.GLB` file's directory table is always encrypted
     this way; there is no per-file or per-table opt-out.

2. **An individual item's payload bytes are *conditionally* re-encrypted**,
   controlled by that item's own `opt` field from its directory entry
   (`GLB_NORMAL` = 0 = plain, `GLB_ENCODED` = 1 = encoded,
   `GFX/GLBAPI.H:43-44`), recorded at load time as the `ITF_ENCODED` bit
   (`0x40000000`, `GFX/GLBAPI.C:81`) on the in-memory `ITEMINFO.flags`.
   - Decryption of the payload happens in `GLB_Load()`, immediately after
     the raw bytes are read off disk:
     ```c
     lseek( handle, ii->offset, SEEK_SET );
     read( handle, ( VOID * ) inmem, ii->size );
     #ifdef _SCOTTGAME
     if ( ii->flags & ITF_ENCODED )
     {
        GLB_DeCrypt( serial, inmem, ii->size );
     }
     #endif
     ```
     (`GFX/GLBAPI.C:428-435`.) Same key `"32768GLB"`, same cipher, but this
     time called **once over the item's entire payload** (`ii->size`
     bytes) — a single continuous keystream over the whole item, not
     restarted every 28 bytes the way the directory is.
   - Whether any given real item in `FILE0000.GLB`/`FILE0001.GLB` actually
     has `ITF_ENCODED` set is a per-file, per-item fact baked into that
     specific archive's directory table (the `opt` field) — it cannot be
     determined from the code alone. A reader must check the decrypted
     `opt`/`ITF_ENCODED` flag for each entry and only decrypt payloads that
     have it set; decrypting an already-plaintext payload will corrupt it.

3. **The same cipher primitive is reused elsewhere in the game with a
   different key** — `SOURCE/LOADSAVE.C:149,261,266,338,344,346` calls
   `GLB_EnCrypt`/`GLB_DeCrypt` with key `gdmodestr` to obfuscate save-game
   structures (`PLAYEROBJ`, `OBJ`). This is **unrelated to the `.GLB` archive
   format** — noted here only so it isn't mistaken for a second archive-file
   cipher key when grepping the codebase.

**No compression of any kind** is present anywhere in `GLBAPI.C`/`GLBAPI.H`
— `filesize` is the exact byte count read via a single `read()` call
(`GFX/GLBAPI.C:429`), copied to the output buffer as-is once decrypted.
**No checksum/CRC** of any entry or of the file as a whole is computed,
stored, or verified anywhere in this source.

---

## 4. Item lookup

Two lookup mechanisms exist, both ultimately keyed off the same 32-bit
`handle` scheme, defined identically (field-for-field) in two places:
`ITEMS` in the public header (`GFX/GLBAPI.H:33-37`, declared but effectively
unused externally) and the internal `ITEM_ID`/`ITEM_H` union actually used
by all the runtime functions (`GFX/GLBAPI.C:66-76`):

```c
typedef struct { WORD itemnum; WORD filenum; } ITEM_ID;
typedef union  { ITEM_ID id; DWORD handle; } ITEM_H;
```

Because `itemnum` is declared first and x86 is little-endian, `itemnum`
occupies the **low 16 bits** of the 32-bit `handle` and `filenum` occupies
the **high 16 bits**: `handle = (filenum << 16) | itemnum`. This is
independently confirmed by the generated constants in `SOURCE/FILE0001.INC`,
e.g. `#define CURSOR_PIC 0x00010012 //ITEM:018` — high word `0x0001` =
file 1 (`FILE0001.GLB`), low word `0x0012` = 18 (decimal), matching the
`//ITEM:018` comment exactly. Likewise `SOURCE/FILE0000.INC:3` `#define
ATENTION_TXT 0x00000000` is file 0, item 0.

- **`~0` (all bits set, `0xFFFFFFFF`) is the reserved "empty/invalid handle"
  sentinel** — same value as the `EMPTY` macro (`SOURCE` headers). Checked
  explicitly at the top of `GLB_FetchItem`, `GLB_UnlockItem`, `GLB_IsLabel`,
  `GLB_ReadItem` (e.g. `GFX/GLBAPI.C:456-460`, `:558-559`, `:597-598`,
  `:623-624`).

- **By-index lookup** (`GLB_Load`, `GFX/GLBAPI.C:401-439`): takes explicit
  `filenum`/`itemnum` `INT`s (not a packed handle). Bounds are only checked
  via `ASSERT` (`GFX/GLBAPI.C:411,417`), which **compiles to a no-op unless
  `DEBUG` is defined** (`GFX/EXITAPI.H:33,41` — see §6). It indexes directly:
  `ii = filedesc[filenum].item; ii += itemnum;` (`GFX/GLBAPI.C:419-420`) —
  i.e., a flat array index into the in-memory `ITEMINFO[]` built by
  `GLB_LoadIDT()`, which is 1:1 with directory-table order (§2). No
  hashing, no binary search — it's a direct array offset.

- **By-handle lookup** (`GLB_FetchItem`/`GLB_ItemSize`/`GLB_IsLabel`/
  `GLB_ReadItem`/`GLB_FreeItem`/`GLB_UnlockItem`, all in `GFX/GLBAPI.C`):
  unpack the `DWORD handle` into `filenum`/`itemnum` via the union, then
  same flat-array indexing as above, e.g. `GFX/GLBAPI.C:462-468`.
  `GLB_GetItem(handle)` / `GLB_LockItem(handle)` / `GLB_CacheItem(handle)`
  all funnel through the shared helper `GLB_FetchItem()`
  (`GFX/GLBAPI.C:446-512`), which allocates a buffer sized `ii->size` and
  calls `GLB_Load()` (the by-index loader) to actually populate it
  (`GFX/GLBAPI.C:495`) — so by-handle lookup is a thin wrapper over
  by-index lookup plus a memory-management/caching layer (locking,
  optional virtual-memory paging via `VM_Malloc`/`VM_Touch`/`VM_Lock`, not
  part of the file format itself).
  - `GLB_ItemSize(handle)` (`GFX/GLBAPI.C:775-794`) just returns `ii->size`
    for the resolved entry — no I/O, pure directory-table lookup.
  - `GLB_IsLabel(handle)` (`GFX/GLBAPI.C:589-609`) returns `ii->size == 0`
    — i.e., "is this a label" is defined purely as "does the directory
    entry have `filesize == 0`" (see §2/§3).

- **By-name lookup** (`GLB_GetItemID`, `GFX/GLBAPI.C:644-677`): **linear
  scan** over every loaded `.glb` file (`filenum` from 0 to `num_glbs-1`,
  the count passed to `GLB_InitSystem`) and every item within each file
  (`itemnum` from 0 to `filedesc[filenum].items-1`), comparing
  `stricmp( ii->name, in_name ) == 0` (`GFX/GLBAPI.C:666`) — a
  **case-insensitive** C-string compare. First match wins; returns
  `ITEM_H.handle` built from the matching `filenum`/`itemnum`
  (`GFX/GLBAPI.C:668-670`). Returns the `~0` empty sentinel if `in_name` is
  empty/space (`GFX/GLBAPI.C:658`) or if nothing matched
  (`GFX/GLBAPI.C:676`). There is **no name index/hash table** — every
  by-name call is O(total items across all open files). See §6 for a
  correctness trap in this comparison (16-byte, not-necessarily-terminated
  `ii->name`).

- **Handle arithmetic is used deliberately in game code**: because
  `itemnum` is just a small integer in the low word, and consecutive items
  in the same GLB file get consecutive handle values, the game does plain
  integer arithmetic on handles to walk ranges. Example, `SOURCE/HELP.C:
  25-34`:
  ```c
  startitem = GLB_GetItemID ("STARTHELP");
  enditem   = GLB_GetItemID ("ENDHELP");
  if ( !reg_flag ) startitem += (DWORD)2;
  maxpages = ( enditem - startitem - 1 );
  startitem++;
  ```
  This only works because `STARTHELP` and `ENDHELP` are label markers
  (`filesize==0`) bracketing a contiguous run of items *within the same
  file* — subtracting/incrementing handles is really subtracting/
  incrementing `itemnum` as long as no arithmetic carries into the
  `filenum` high word. See §6.

`GLB_GetPtr()` (`GFX/GLBAPI.H:131-137`) is declared in the header but its
only implementation in `GFX/GLBAPI.C:679-703` is wrapped in `#if 0` (dead
code, references a `memory` field that doesn't even exist on `ITEMINFO`
anymore) — **not part of the live format/API**, ignore it.

---

## 5. Palette and image/sprite payload formats

The directory entry (§2) carries no type tag — what a payload *is* is
determined by convention (which slot the game asked for) and, for images,
by a small struct embedded at the very start of the decrypted payload
bytes.

### 5a. Palette (`PALETTE_DAT`, `SOURCE/FILE0001.INC:3`, handle `0x00010000`
→ file 1, item 0)

- Raw payload is **768 bytes**: 256 palette entries × 3 bytes each, **RGB
  triplet order**, one byte per channel, **no header of any kind** — it is
  loaded straight into a `BYTE *` and indexed as `palette[i*3+0..2]`.
  Confirmed by the consumer, `GFX_GetPalette()` (`GFX/GFXAPI.C:284-296`,
  loop `for (loop = 0; loop < 768; loop++) *curpal++ = inp(0x3c9);`) and by
  the setter `GFX_SetPalette()` (`GFX/GFXAPI.C:182-211`, `palette += (
  start_pal * 3 )`, then a loop writing 3 bytes per color to VGA DAC port
  `0x3C9`).
  - **Values are raw VGA DAC 6-bit values, range 0–63 per channel, NOT
    0–255.** The code writes each byte directly to the hardware DAC data
    port (`outp(0x3C9, *palette++)`, `GFX/GFXAPI.C:210`) with no scaling —
    real VGA DAC registers only accept 6-bit (0–63) intensities. A port
    that wants to render this palette in a modern (8-bit/channel) context
    must scale each value, typically `v8 = (v6 * 255) / 63` or `(v6 << 2) |
    (v6 >> 4)`; nothing in this source does that scaling for you, it's a
    property of the original VGA hardware, not the file format.
  - Loaded in-game via `tptr = GLB_LockItem ( PALETTE_DAT );` then `memset (
    tptr, 0, 3 );` (`SOURCE/RAP.C:1656-1657`) — **note the game explicitly
    zeroes the first palette entry's 3 bytes (index 0, i.e. RGB
    0,0,0)** after loading, forcing palette slot 0 to pure black regardless
    of what's stored on disk. This is a runtime override, not something a
    format-level reader needs to replicate unless matching in-game visuals
    exactly — but it does mean the *raw bytes on disk* for palette index 0
    are not necessarily black even though they always render black in the
    actual game.

### 5b. Images / sprites (`*_PIC` items, e.g. `SHLDLOW_PIC`, `WEPDEST_PIC`,
`CURSOR_PIC`, `MENU1_PIC`, etc.)

Every image payload begins with a `GFX_PIC` header, defined
`GFX/GFXAPI.H:38-45`:
```c
typedef enum { GSPRITE, GPIC } GFX_TYPE;   // GFX/GFXAPI.H:31 — GSPRITE=0, GPIC=1

typedef struct
{
   GFX_TYPE type;    // 4 bytes (INT-sized enum in this build) — GSPRITE or GPIC
   INT      opt1;    // 4 bytes, unused by the parsers examined
   INT      opt2;    // 4 bytes, unused by the parsers examined
   INT      width;   // 4 bytes
   INT      height;  // 4 bytes
} GFX_PIC;            // total 20 bytes, all fields 4-byte little-endian ints
```
The `type` field (first 4 bytes of every image payload) is what
distinguishes the two payload sub-formats — checked in
`GFX_PutImage()`: `if ( h->type == GSPRITE ) { GFX_PutSprite(...); } else {
/* raw raster path */ }` (`GFX/GFXAPI.C:1417-1445`).

**Format A — `GPIC` (type == 1): raw indexed raster.**
- Immediately after the 20-byte `GFX_PIC` header: `width * height` raw
  bytes, **one byte per pixel, 8-bit palette index, row-major, no
  padding**, stride exactly equal to `width` (no alignment padding per
  row). Confirmed by `GFX_PutImage()`'s non-sprite branch, which advances
  `image += sizeof(GFX_PIC)` (`GFX/GFXAPI.C:1428`) and then blits via
  `GFX_PutPic()`/`GFX_PutMaskPic()`, whose assembly bodies do straight
  `rep movsb/movsw/movsd` byte copies row by row with `esi += gfx_imga`
  (the original unclipped image width) advancing one source scanline at a
  time — i.e. a flat `width*height` byte array, nothing more.
  - Two draw variants: `GFX_PutPic()` (`GFX/GFXAPI_A.ASM:311-360`, opaque
    block copy, every byte written unconditionally) vs. `GFX_PutMaskPic()`
    (`GFX/GFXAPI_A.ASM:365-410`) — comment at `GFX/GFXAPI_A.ASM:363`:
    "Puts Picture into buffer with color 0 see thru", and the body confirms
    it literally, per-pixel: `mov al,[esi][ecx]; or al,al; jnz
    @Mask_PutPic` (`GFX/GFXAPI_A.ASM:386-388`) — only writes the
    destination byte when the source pixel value is **non-zero**. I.e. for
    masked blits, **palette index 0 is the transparent/chroma-key color**,
    tested per-pixel-value at draw time, not encoded specially in the file
    itself; the pixel bytes are identical between masked and unmasked
    images, only the *draw call* differs.
  - No compression, no RLE for this format — it's a literal bitmap.

**Format B — `GSPRITE` (type == 0): sparse run-segment list (used for
game sprites — ships, cursor, etc., where most of the bounding box is
transparent).**
- Immediately after the 20-byte `GFX_PIC` header comes a sequence of
  variable-count **run segments**, each prefixed by a 16-byte `GFX_SPRITE`
  header (`GFX/GFXAPI.H:47-53`):
  ```c
  typedef struct
  {
     INT x;       // 4 bytes — x position of this run within the sprite's bounding box
     INT y;       // 4 bytes — y position (row) of this run
     INT offset;  // 4 bytes — precomputed linear buffer offset for the fast/unclipped blit path (see below); ALSO doubles as the end-of-list sentinel
     INT length;  // 4 bytes — number of opaque pixel bytes that immediately follow this 16-byte header
  } GFX_SPRITE;     // total 16 bytes; confirmed == SPRITE_S_SIZE (GFX/GFXAPI_A.ASM:25, "SPRITE_S_SIZE = 16")
  ```
  followed immediately by exactly `length` raw pixel-index bytes (the
  opaque run itself — literal bytes, no compression). Then the next 16-byte
  `GFX_SPRITE` header + its run bytes, and so on.
  - **Terminator**: the segment list ends when a `GFX_SPRITE.offset` field
    equals `EMPTY` (`~0` == `0xFFFFFFFF`) — checked as `while ( ah->offset
    != EMPTY )` in the C clipped-draw path inside `GFX_PutSprite()`
    (`GFX/GFXAPI.C:1489`), and equivalently in hand-written assembly (the
    unclipped fast path, `GFX_DrawSprite`) as a 16-bit compare on the low
    half of that same field: `cmp WORD PTR bx, 0ffffH`
    (`GFX/GFXAPI_A.ASM:204`, reading the word at `+8` = the `offset`
    field's low 16 bits). **There is no count of segments stored
    anywhere** — a reader must scan segment headers until it finds one
    whose `offset` (or at least its low 16 bits) is `0xFFFF`/`0xFFFFFFFF`;
    that terminator header itself has no trailing pixel bytes (its own
    `length` field is not meaningful/consumed).
  - Two redundant position encodings are present per segment: explicit
    `x`/`y` (row/column within the sprite), used by the **clipped** C draw
    path which recomputes `ox = ah->x + x; oy = ah->y + y;` then `memcpy(
    displaybuffer + ox + ylookup[oy], outline, lx )`
    (`GFX/GFXAPI.C:1493-1506`); and a precomputed absolute `offset`, used by
    the **fast/unclipped** path (`GFX_DrawSprite`, pure assembly,
    `GFX/GFXAPI_A.ASM:193-225`), which just does `edi = dest + offset` and
    copies `length` bytes with no recomputation. **Both fields must be
    correct and mutually consistent in a valid file** — a reader that only
    implements one draw path (e.g. a JS canvas renderer) should just use
    `x`/`y` (safer, position is self-describing) and can ignore `offset`
    except as the `0xFFFF...` terminator check.
  - Pixel bytes within a run are raw 8-bit palette indices, same convention
    as Format A — no run-internal compression, `length` is a literal byte
    count to copy verbatim.
  - Unlike Format A, there is **no explicit transparent-color convention**
    for Format B — transparency is structural: pixels simply outside any
    run segment are never touched by the blit, so nothing is drawn there
    at all (as opposed to Format A's masked mode, which draws every pixel
    but skips ones matching a magic color value).

`GFX_OverlayImage()` (`GFX/GFXAPI.C:1447-1470`) is a third, narrower
compositing helper (stamps one already-in-memory `GPIC` raster onto
another) — not a distinct file payload format, just another consumer of
Format A bytes. Note its inner loop skips column index `255` specifically
(`if ( i != 255 ) *baseimage = *overimage;`, `GFX/GFXAPI.C:1466-1467` — `i`
there is the horizontal pixel loop counter, **not** a pixel value check);
flagged in §6 as a quirk, not a general format rule — don't generalize "255
is special" from this one call site.

---

## 6. Quirks, traps, and DOS-specific assumptions for a JS reimplementation

1. **32-bit fields, not 16-bit.** Despite this being 1994 DOS code, the
   game is compiled flat 32-bit (Watcom, `.386`/`FLAT` model,
   `GFX/GFXAPI_A.ASM:16`), so every `DWORD`/`INT` field in `KEYFILE`,
   `GFX_PIC`, and `GFX_SPRITE` is 4 bytes, not 2. Don't assume classic
   16-bit-DOS struct packing — verify against the `//ITEM:NNN` values in
   the `.INC` files (§4) if unsure; they only line up if you read `KEYFILE`
   as 28 bytes (3×4-byte fields + 16 raw bytes) and directory records as
   contiguous 28-byte blocks.

2. **The directory table is always encrypted; item payloads are only
   sometimes encrypted, and it's a per-item on/off flag you must read from
   the (already-decrypted) directory, not something you can assume from
   the item's apparent type.** Decrypt the 28-byte header/entries
   unconditionally; decrypt payload bytes only when that entry's `opt`
   field (post directory-decrypt) equals `GLB_ENCODED` (1). Getting this
   backwards (e.g. decrypting every payload, or none) will silently corrupt
   or garble a subset of items rather than fail loudly.

3. **The cipher keystream restart boundary matters and differs between the
   two use sites**: restarts every 28 bytes for directory entries (each
   `KEYFILE` decrypted independently, §3), but runs continuously across an
   entire item's payload in one pass (§3). A byte-for-byte-correct port
   must replicate exactly where the keystream resets.

4. **No magic bytes, no format version, no checksum anywhere.** A reader
   has no cheap way to validate "is this actually a GLB file" beyond
   successfully decrypting record 0 into a plausible item count and then
   successfully parsing that many 28-byte records without running off the
   end of the file. Malformed input degrades silently rather than raising
   a clear format error in the original code (see next point).

5. **Bounds checking is compiled out in release builds.** Every
   `filenum`/`itemnum` range check in `GLBAPI.C` is an `ASSERT(...)` call —
   `GFX/GLBAPI.C:160` (`GLB_FindFile`), `:205` (`GLB_OpenFile`), `:263`
   (`GLB_NumItems`), `:411,417` (`GLB_Load`), `:464-465` (`GLB_FetchItem`),
   `:563-564` (`GLB_UnlockItem`), `:602-603` (`GLB_IsLabel`), `:630-631`
   (`GLB_ReadItem`), `:721` (`GLB_FreeItem`, filenum only), `:788-789`
   (`GLB_ItemSize`) — and `ASSERT` is defined to `((void)0)` — a total
   no-op — unless the C macro `DEBUG` is defined (`GFX/EXITAPI.H:33,41`).
   The released game therefore performs **no bounds checking** on
   handle/index values at almost any accessor; an out-of-range `itemnum`
   just walks off the end of the in-memory `ITEMINFO[]` array. The one
   exception is `GLB_FreeItem()`, which additionally does an **explicit,
   unconditional** `itemnum` range check via `if ( itm.id.itemnum >= (
   WORD ) filedesc[ itm.id.itemnum ].items ) EXIT_Error(...)`
   (`GFX/GLBAPI.C:722-726`) — a real `if`/`EXIT_Error`, not an `ASSERT`, so
   it still runs in release builds — inconsistent with every other
   accessor, which has no such fallback. A robust JS port should add its
   own bounds checking everywhere rather than mirroring the (mostly
   absent) original behavior.

6. **Item names are exactly 16 raw bytes and are NOT guaranteed
   null-terminated on disk.** The `KEYFILE.name` comment says "end with
   null" (`GFX/GLBAPI.H:30`) but nothing enforces it, and the copy into the
   in-memory `ITEMINFO.name[16]` is a fixed 16-byte `memcpy`
   (`GFX/GLBAPI.C:318`) with **no extra byte for a guaranteed terminator**.
   Since `ITEMINFO.name` is the *first* member of the `ITEMINFO` struct
   (`GFX/GLBAPI.C:47-55`), a 16-byte name with no embedded NUL would cause
   the original C code's `stricmp()` in `GLB_GetItemID()`
   (`GFX/GLBAPI.C:666`) to read past the array into the adjacent `vm_mem`
   field until it happens to hit a zero byte — undefined behavior in C, and
   not something a JS port should replicate. **When porting, always treat
   the name as "up to 16 bytes, stop at the first `\0` if present, ignore
   anything after byte 16"** rather than relying on C-string semantics.

7. **Handle arithmetic (`+`, `-`, `++`) is used as an intentional API
   pattern by game code** to walk ranges of items within one file (see
   `SOURCE/HELP.C:25-34` in §4) — because `itemnum` sits in the low 16
   bits, plain integer `+`/`-` on a handle is really `+`/`-` on `itemnum`,
   *as long as it never carries into/out of the high 16 bits*
   (`filenum`). A JS port representing handles as, say, `{filenum,
   itemnum}` objects instead of packed 32-bit integers must special-case
   any code path that does this kind of arithmetic (or just keep packed
   `u32` handles and replicate the C integer semantics exactly).

8. **"Label" entries (`filesize == 0`) are real, load-bearing directory
   rows, not just documentation artifacts.** They mark file-position
   boundaries used by range math (see point 7) — a reader that filters
   them out of the item list (e.g. "skip zero-size entries") will break
   any handle-arithmetic-based range logic that depends on their exact
   `itemnum` position. Keep them as normal entries with `size == 0` and let
   `GLB_IsLabel`-equivalent logic (`size === 0`) identify them, don't drop
   them from the array.

9. **File naming and lookup path are DOS 8.3-flavored but not
   case-sensitive-relevant on modern filesystems**: `sprintf( filename,
   "%s%04u.glb", prefix, filenum )` (`GFX/GLBAPI.C:165`) — default `prefix`
   is the literal `"FILE"` (`GFX/GLBAPI.C:41`); callers may override it via
   `GLB_InitSystem`'s `iprefix` argument, in which case it's copied and then
   uppercased via `strupr()` (`GFX/GLBAPI.C:363-369`) — Raptor's own calls
   always pass `NUL` for `iprefix` (`SOURCE/RAP.C:1616,1620`), so in
   practice the prefix is always `"FILE"`. Zero-padded 4-digit file number,
   literal lowercase `.glb` extension in
   the format string (irrelevant on case-insensitive filesystems, but note
   it if a port does a case-sensitive lookup). It tries the current
   directory first, then falls back to a path derived from the running
   executable's own path (`argv[0]`) with the trailing filename stripped
   (`GFX/GLBAPI.C:165-178`, `GLB_FindFile`). `MAX_GLB_FILES` is `0x0F` = 15
   (`GFX/GLBAPI.H:40`); the actual game only opens 2 (`GLB_InitSystem(
   argv[0], 2, NUL )`, shareware/unregistered) or 6
   (`GLB_InitSystem( argv[0], 6, NUL )`, registered) of them
   (`SOURCE/RAP.C:1616,1620`). `FILE0000.GLB`/`FILE0001.GLB` existence is
   explicitly probed with `access()` before anything else at
   `SOURCE/RAP.C:1498,1521` (also `1501,1504` for the higher-numbered
   episode files) — the game refuses to start at all if
   `FILE0000.GLB` is missing (`SOURCE/RAP.C:1521-1524`).

10. **No near/far pointer segment tricks in the GLB reader itself** — this
    module is pure 32-bit flat-model C/asm (see point 1), so there's none
    of the classic 16-bit-DOS `huge`/`far`/segment:offset arithmetic to
    worry about when porting the archive-parsing code. (DOS segment
    tricks *do* appear elsewhere in this codebase, e.g. `GFX_InitSystem()`
    in `GFX/GFXAPI.C:213-249` allocating real-mode DOS memory via
    `_dpmi_dosalloc` and computing a flat pointer as `segment << 4`, and
    `displayscreen = (BYTE *)0xa0000` for the VGA framebuffer — but these
    are video/display-buffer concerns, not part of the `.GLB` file format,
    and don't need to be replicated by a port that just extracts/decodes
    archive contents.)

11. **`GLB_UseVM()` / virtual-memory caching (`fVmem`, `VM_Malloc`,
    `VM_Lock`, `VM_Touch`, `VM_Free`) is a runtime memory-management
    convenience layer for the original DOS game (paging item buffers out
    under low-memory conditions) and has nothing to do with the on-disk
    format** — a JS port doesn't need any equivalent; every item can just
    be decoded to a normal in-memory buffer on demand.

12. **`GLB_GetPtr()` is dead code** (`#if 0` around its only body,
    `GFX/GLBAPI.C:679-703`) and additionally references a struct field
    (`ii->memory`) that doesn't exist in the live `ITEMINFO` definition —
    do not treat its declared signature in `GFX/GLBAPI.H:134-137` as
    describing real, working behavior.

---

## Appendix — quick reference

**Directory record (`KEYFILE`), 28 bytes, little-endian, always
cipher-encrypted on disk:**
| offset | size | field | meaning |
|---|---|---|---|
| 0 | 4 | `opt` | `0` = normal, `1` = payload is additionally encrypted (`GLB_NORMAL`/`GLB_ENCODED`) |
| 4 | 4 | `offset` | absolute file offset of payload (record 0 only: repurposed as item count `N`) |
| 8 | 4 | `filesize` | payload length in bytes; `0` ⇒ this is a "label" marker, no payload |
| 12 | 16 | `name` | up to 16 ASCII bytes, may fill all 16 with no terminator |

**File layout:** byte 0 = pseudo-header (`KEYFILE`, gives `N` via its
`offset` field) → bytes 28..28+28N = `N` real directory entries, in
item-index order → payload bytes wherever each entry's `offset` points.

**Cipher:** additive chained stream cipher, key `"32768GLB"` (directory) or
per-caller key (elsewhere in the game, not archive-related), start index
`SEED % strlen(key)` with `SEED = 0x19 = 25`, `ciphertext[i] = (plain[i] +
key[idx] + ciphertext[i-1]) % 256`.

**Handle:** 32-bit, little-endian packed = `(filenum << 16) | itemnum`.
Sentinel `0xFFFFFFFF` = empty/invalid.

**Image header (`GFX_PIC`), 20 bytes at the start of every image payload:**
`type`(4, 0=`GSPRITE`/1=`GPIC`), `opt1`(4), `opt2`(4), `width`(4),
`height`(4).
- `type==GPIC`: raw `width*height` indexed bytes follow, row-major, no
  padding. Mask draw treats palette index `0` as transparent.
- `type==GSPRITE`: sequence of 16-byte `GFX_SPRITE` run headers
  (`x`(4),`y`(4),`offset`(4),`length`(4)) each followed by `length` raw
  indexed pixel bytes, terminated by a header whose `offset == 0xFFFFFFFF`.

**Palette payload:** 768 raw bytes, 256×RGB, no header, VGA 6-bit-per-channel
(0–63) values.
