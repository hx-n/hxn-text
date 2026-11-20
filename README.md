# hxn-text

Fonts, text shaping, glyph rasterization and atlas data for Haxe, using the
shared `blinc_text` engine. Applications own drawing and GPU textures.

```haxe
import hxn.text.Font;
import hxn.text.TextEngine;
import hxn.text.AtlasKind;

final font = new Font(haxe.Resource.getBytes("regular-font"), {});
final engine = new TextEngine();
final text = engine.prepare(font, "Hello, Haxe", {size: 24});
final atlas = engine.atlas(AtlasKind.Coverage, 0);
// Upload atlas.pixels, then draw text.glyphs with the application renderer.
font.close();
engine.close();
```

Pass font bytes from hxn-file, an annotated hxn-assets field or another loader.
`Font` supports TTF, OpenType collections and WOFF2. A collection selects
`faceIndex`; `weight` selects the variable font's weight axis. Static styles
need the corresponding font face. Native applications can use `Font.system`.
Browser applications supply their own fonts.

`font.shape` returns glyph IDs, advances, offsets and UTF-8 byte clusters for
a segment. `font.rasterize` returns an owned coverage or straight-RGBA bitmap.
`engine.prepare` supplies positioned atlas rectangles and text measurements.
Pass each texture consumer's last revision to `engine.atlas` for incremental
updates. Atlas coordinates are pixels. Normalize them against the current
texture dimensions when drawing. Compare `generation` before reusing geometry
after clearing an engine.

Published packages contain the native adapters. A Haxe application compiles
with `-lib hxn-text` and does not build the engine. For source development:

```sh
hxn check hl --vm ash
hxn check cpp cppia
hxn package hl cpp --release --out target/package
```

Read [the API contract](docs/design.md), [contributor conventions](docs/conventions.md)
and [test coverage](tests/README.md). Fonts and native dependencies retain their
own licenses. CSS, UI/container layout, scene composition and rendering belong
to hxnme or the consuming application.
