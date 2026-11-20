import hxn.text.AtlasKind;
import hxn.text.AtlasUpdate;
import hxn.text.Font;
import hxn.text.TextEngine;
import haxe.io.Bytes;

class Main {
	static function require(value:Bool, message:String):Void {
		if (!value)
			throw message;
	}

	static function fixture(name:String):Bytes {
		final bytes = haxe.Resource.getBytes(name);
		if (bytes == null)
			throw 'missing font $name';
		return bytes;
	}

	static function apply(texture:Bytes, update:AtlasUpdate):Void {
		final bpp = update.kind == AtlasKind.Color ? 4 : 1;
		for (row in 0...update.patchHeight)
			texture.blit(((update.y + row) * update.width + update.x) * bpp, update.pixels, row * update.stride, update.stride);
	}

	static function main():Void {
		final source = fixture("latin");
		final bytes = Bytes.alloc(source.length);
		bytes.blit(0, source, 0, source.length);
		final font = new Font(bytes, {});
		bytes.fill(0, bytes.length, 0);
		final run = font.shape("office", 24);
		require(run.width > 0 && run.glyphs.length < 6, "owned font and ligatures");
		final mask = font.rasterize(run.glyphs[0].glyphId, 24, AtlasKind.Coverage);
		require(mask.width > 0 && mask.pixels.length == mask.stride * mask.height, "glyph mask");
		for (sample in [
			{name: "arabic", text: "مرحبا بالعالم"},
			{name: "devanagari", text: "नमस्ते दुनिया"}
		]) {
			final face = new Font(fixture(sample.name), {});
			require(face.supports(sample.text), "font coverage");
			final shaped = face.shape(sample.text, 20);
			final utf8 = Bytes.ofString(sample.text);
			require(shaped.width > 0, "shaped width");
			for (glyph in shaped.glyphs) {
				require(glyph.glyphId > 0, "missing script glyph");
				require(glyph.cluster < utf8.length && (utf8.get(glyph.cluster) & 0xC0) != 0x80, "UTF-8 cluster boundary");
			}
			face.close();
		}
		final engine = new TextEngine();
		final text = engine.prepare(font, "Hello", {});
		require(text.glyphs.length > 0 && text.width > 0, "prepared text");
		final first = engine.atlas(AtlasKind.Coverage, 0);
		require(first.full && first.pixels.length == first.width * first.height, "full atlas");
		require(engine.atlas(AtlasKind.Coverage, first.revision).pixels.length == 0, "unchanged atlas");
		engine.prepare(font, "W", {});
		final patch = engine.atlas(AtlasKind.Coverage, first.revision);
		require(!patch.full && patch.revision > first.revision, "incremental atlas");
		apply(first.pixels, patch);
		final full = engine.atlas(AtlasKind.Coverage, 0);
		require(first.pixels.compare(full.pixels) == 0, "patch matches full snapshot");
		final other = engine.atlas(AtlasKind.Coverage, first.revision);
		require(other.pixels.compare(patch.pixels) == 0, "independent consumer");
		font.close();
		final generation = engine.generation();
		engine.clearFonts();
		require(engine.generation() != generation, "stale geometry generation");
		engine.close();
		var rejected = false;
		try {
			final invalid = new Font(Bytes.ofString("invalid"), {});
			invalid.close();
		} catch (_:hxn.text.TextException) {
			rejected = true;
		}
		require(rejected, "typed invalid font error");
		Sys.println("PASS: owned fonts, multi-script shaping, glyph masks and independent atlas updates");
		final nonce = haxe.Resource.getString("hxn-text-test-nonce");
		if (nonce != null)
			Sys.println("hxn-text-test:" + nonce);
		hxn.Loop.exit(0);
	}
}
