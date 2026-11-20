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

Install a prebuilt release or CI ZIP with `haxelib install hxn-text-0.1.0.zip`,
then compile with `-lib hxn-text`. The ZIP contains the Haxe bindings and native
libraries for desktop, mobile, Ash wasm and Emscripten. Applications need Haxe
and their selected runtime, without Rust or a source checkout.

The repository keeps its generated `binding/`, `include/`, `haxelib.json` and
`extraParams.hxml` at the package root. CI builds platform binaries, assembles
the Haxelib and runs installed consumers with Rust disabled. Native binaries
are release artifacts and are excluded from Git.

Font assets use `-lib hxn-assets` with `FontAssets.decode` as the runtime decoder:

```haxe
@:build(hxn.assets.Assets.build())
class GameAssets {
    @:asset("fonts/ui.ttf") @:contentAddressed
    @:dynamicAsset @:assetDecode(hxn.text.FontAssets.decode)
    public static var Ui:hxn.text.Font;
}
```

Read `GameAssets.Ui` after `GameAssets.load(loader)` completes. For direct
address-based loading, `FontAssets.load(loader, address, options)` returns a
future with a new owned font. The [runnable font asset example](examples/assets)
loads a bundled font, prepares text and releases its resources.

Read [the API contract](docs/design.md), [contributor conventions](docs/conventions.md)
and [test coverage](tests/README.md). Fonts and native dependencies retain their
own licenses. CSS, UI/container layout, scene composition and rendering belong
to hxnme or the consuming application.
