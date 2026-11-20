# Font and text data

The Rust library wraps `blinc_text`. HarfRust shapes text, swash rasterizes
glyphs, and Blinc manages font discovery and the coverage and color atlases.
The library has no window, CSS, UI tree or GPU device. Font fetching belongs
to the application's asset or file loader.

## Fonts

`new Font(bytes, options)` copies the bytes and validates the selected face.
Input data can change after the call. `faceIndex` selects a collection face;
`weight` is 1..1000 and applies the same variable axis to shaping and
rasterization. Native `Font.system(family, weight, italic)` uses Blinc's
platform discovery. Browser programs supply bytes instead.

Font bytes are immutable and shared by retained owners. An engine retains each
font it prepares, so closing the caller's handle leaves existing geometry and
atlas pixels valid. `clearFonts` releases those retained fonts and caches.
`Font.close` and `TextEngine.close` release their Haxe handles. Returned glyph
runs, bitmaps and atlas patches own their data and survive those calls.

Input fonts and decoded WOFF2 data are bounded to 64 MiB. WOFF2 inherits the
upstream decoder's format support, including its transformed-hmtx limitation.
Malformed fonts and invalid options throw `TextException`, whose `error` holds
a code and message. A system lookup can fail when the requested font is absent.
Do not use system fallback as proof of bundled-font coverage on another platform.

## Shaping and preparation

`Font.shape(text, size)` shapes one segment with Blinc's inferred segment
properties. Glyph advances and offsets are logical pixels. `cluster` identifies
a UTF-8 byte offset, not a Haxe string or UTF-16 index. Related glyphs can share
a cluster, and right-to-left output can report decreasing clusters.

`TextEngine.prepare` delegates wrapping and glyph preparation to Blinc.
`size`, `maxWidth`, line-height and letter spacing describe text, not UI boxes.
`scale` selects device pixels per logical pixel, including application zoom.
Geometry comes back in logical pixels and atlas rectangles in device pixels.
Optional horizontal subpixel phases suit axis-aligned text. Rotated or skewed
text needs the application's own sampling policy.

Each call accepts at most 64 KiB of UTF-8 text. Font size is 0.5..256 logical
pixels; device scale is 1/16..16 and the resulting raster size is at most 256.
An engine retains at most 256 explicitly used faces. All values must be finite.
The wrapper inherits Blinc's current paragraph, fallback and size-cache rules.
Its segment shaping API does not by itself implement full paragraph bidi
itemization or arbitrary cross-script fallback. Cover those cases explicitly
before treating a renderer as a complete multilingual paragraph system.

## Atlas delivery

Coverage patches contain one byte per pixel. Color patches contain straight
RGBA bytes. `stride` is the packed patch row size. The patch is placed at
`x`, `y` inside a texture of `width`, `height`.

Each consumer passes its own last revision to `atlas(kind, seenRevision)`.
Unchanged revisions return no pixels. Revision zero requests a complete
snapshot. The engine retains 32 change records per atlas; an older consumer,
a future revision or a texture resize gets a complete snapshot when needed.
A patch remains owned after later calls and is not an acknowledgement shared
between consumers.

Prepared rectangles store atlas pixel coordinates. Atlas growth preserves
those coordinates. Normalize them with the texture's current size when drawing.
`clear` and `clearFonts` change the generation and invalidate earlier geometry.
An exhausted atlas returns `AtlasFull`; the engine does not silently clear
rectangles that the application still uses. The application can clear and
rebuild its batches explicitly.

Native font bytes and atlas storage participate in hxn's allocation accounting.
The shared logger uses target `hxn.text`. The application owns its sink and
severity threshold; the library leaves that configuration unchanged.
