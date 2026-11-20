# Contributor conventions

Public interfaces and data records are declared in `src/lib.rs`. Private
resource and atlas bookkeeping stays in the adjacent modules. Use hxn's normal
generation and packaging workflow; do not hand-maintain runtime adapters.

Use the same shared engine for measurement, shaping and rasterization. Apply
variable axes before both shaping and drawing. Keep source clusters as UTF-8
byte offsets. Use independent font identities for distinct immutable faces.
Shared engine changes belong in Blinc with its regression tests.

Keep pixel ownership and atlas generations explicit. Test old consumers,
independent consumers, growth, clears and closed owners. Do not silently evict
coordinates returned to an application. Retain bounds for font bytes, text,
font counts and atlas growth. Never expose borrowed native pixel pointers.

The init macro `hxn.text.NativeNames.register()` maps C++ implementation types
to `hxn_text` because the common hxn C++ header already has a `hxn::text`
function. Haxe imports remain under `hxn.text`. Keep this macro in generated
source builds and published extraParams.hxml, and test CPPIA hosts and scripts.
The init macro carries no application workflow or rendering behavior.

Use the installed hxn command, Haxe and the selected runtime in examples.
Test-only hosts, fixtures and runners belong under tests, outside published
application tooling. Validate direct `haxe -lib hxn-text` consumers as well as
source CLI checks. Match the hxn CLI and binding versions.

For dependency changes, refresh third-party notices from the locked metadata.
Include the HashLink support dependency's notices with generated native
bindings. Keep unchanged upstream license bytes and per-font attribution.
Before publication, replace local development paths with public Git revisions,
build the native package targets in CI, and run installed consumers.

Run `cargo fmt --all`, strict Clippy, Rust tests and Haxe formatting. The testing
guide lists runtime and measurement checks. Regenerate API references and
synchronize the skill after the public release reaches haxelib.
