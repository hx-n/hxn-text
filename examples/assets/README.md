# Font assets

Add `-lib hxn-text` and `-lib hxn-assets` to an application. From this directory,
`haxe example.hxml` compiles the example. Run `out/main.hl` with Ash or HashLink.
For hxcpp, replace the `-hl` output with `-cpp out/cpp`. These commands use the
installed native packages and need no Rust compiler. The example enables
Emscripten heap growth so loading fonts and retaining atlas snapshots can exceed
the initial wasm heap. Keep memory budgeting in the application configuration.

`GameAssets.Ui` is a typed `hxn.text.Font`. The asset macro generates its address,
catalog, SHA-256 content ID and asynchronous loading. `@:assetDecode` calls the
library decoder after the loader verifies the bytes. `@:dynamicAsset` is required
because a native font handle is created at runtime and cannot be embedded as a
Haxe value. The font bytes can still be known and hashed at compilation.

`Main` uses `FileSource` to read the staged bundled font. For HTTP(S), select
`RemoteSource` and declare the remote URI with the same dynamic Font type and
decoder. Compilation never fetches remote bytes; omit
`@:contentAddressed` when those bytes are unavailable to the compiler. Read the field after
`GameAssets.load(loader)` completes. Keep browser loading asynchronous with
`then`; do not block the page thread. Browser hosts serve the staged assets and
hxn-file agent. Mobile hosts package assets in the app bundle/APK and initialize
hxn-file's platform context.

`FontPreview` prepares text and returns an owned atlas snapshot for an application
renderer. It closes the decoded font and engine and clears the declaration.
Generated `unload()` clears field bindings; it does not close native font handles.
Close those handles explicitly. Loader byte-cache eviction does not invalidate an
already decoded font, and engines retain fonts until `clearFonts()` or `close()`.

For a font selected by address or with a collection/weight selection, use
`FontAssets.load(loader, address, {faceIndex: 0, weight: 700})`. It returns a new
owned font per call. The loader shares source bytes, not native font handles.
An embedded `@:asset` Bytes field can use `FontAssets.decode(bytes, options)`.
TTF, OpenType collections and WOFF2 follow the normal Font decoder and errors.

The catalog also declares the Noto Sans license so the staged bundle retains
the original SIL Open Font License alongside its font.
