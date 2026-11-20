# Working on hxn-text

Read `docs/design.md` and `docs/conventions.md`. The implementation reuses
`blinc_text`; shared shaping or rasterization fixes belong in Blinc. Do not
copy its engine into this repository or depend on blinc_abi's UI machinery.

Implementation issues belong to this repository's git-bug tracker. The hxnme
M0 parent remains `9729a3b16a066eaeedb9ed0b57d13b6fdb311dd80fa49414e8ea8693bf813f6d`
in hxn. The shared HarfRust migration belongs to Blinc issue
`7f644d9947e67521d5dae7778c42bb091aa8855e3e5c384388f0cb0982eec05a`.
Look at the relevant issues before changing their area. Put plans, measurements,
alternatives and validation history in issues, not status documents.

Keep the core runtime-neutral. Use hxn's generated bindings and shared logger.
Do not retain Haxe callbacks, start native threads in a threadless build or
unwind across the boundary. Keep drawing, CSS, scene state and GPU resources
outside this library. Native allocation ownership must remain explicit.

Run Rust tests, formatting and strict Clippy. Format Haxe before commits.
Run the public Haxe fixture on HashLink, Ash hybrid/JIT/interpreter, hxcpp,
CPPIA, Ash wasm and Emscripten, threaded and threadless where supported.
Run runtime tests under timeouts. Test installed packages without Rust tooling.
Mobile test hosts and runners live under tests; test iOS simulator and Android.
Windows passes only after CI runs. State unavailable platforms explicitly.

Update relevant current-design docs with behavior changes. Skills use absolute
HTTPS documentation links. Pin a public shared-engine revision before release;
include its dependency notices and all redistributed font licenses. Regenerate
the API reference and publish the skill discovery entry after publication.

Commit and push only when asked. Commit messages cite this repository's issue
with its full git-bug ID. Upstream migration commits cite Blinc's own issue.
Do not add AI attribution. Push git-bug metadata only when asked separately.
