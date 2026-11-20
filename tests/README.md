# Validation

`src/tests.rs` exercises copied font input, multi-script shaping against
Blinc's original migration fixtures, glyph bitmap ownership, error bounds,
independent atlas consumers, revision history and font release.

`examples/check/Main.hx` exercises those contracts through generated Haxe
bindings. Run it with `hxn check` on native HashLink, Ash hybrid/JIT/interpreter,
hxcpp and CPPIA. For Ash wasm use `hl --wasm`, with and without `--threads`;
for Emscripten use `cpp --wasm`, with and without `--threads`. Add `--browser`
for actual web-page execution. These runtime invocations need a timeout.

The same fonts and original upstream licenses are in `tests/fixtures`.
`shaping-baseline.tsv` records glyph IDs, font-unit advances, offsets and UTF-8
clusters captured from the original Blinc shaper before migration. The Arabic
and Devanagari variable-font sources are pinned in their SOURCE files.

Shared-engine changes also run Blinc's measurement regressions with the
`text_measurer` feature: unit tests plus fallback_measure, baseline_alignment,
text_overrides, css_line_height, letter_spacing_trailing, rich_text_wrap,
update_text, text_area_interaction and rich_text_link_geometry. Check that
measured widths, wrapping, carets and fallback advances still agree with drawing.

`python3 tests/package.py` builds a complete local SDK and tests direct Haxe
consumers with Rust tooling disabled. Mobile test hosts remain under
`tests/mobile`; `python3 tests/mobile/run.py ios-sim|android hl|cpp --device
<id>` runs the same font/atlas fixture on an iOS simulator or Android. The
runner removes only its own temporary device files. A source compile or a cross-target
build does not establish runtime or pixel correctness. Windows results come
from CI. Report unavailable runtimes instead of marking them passed.
