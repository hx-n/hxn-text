import hxn.assets.AssetLoader;
import hxn.assets.FileSource;
import hxn.file.Storage;

class Main {
	static function main():Void {
		final files = new Storage("dev.hxn.text.font-assets");
		final loader = new AssetLoader(new FileSource(files), GameAssets.catalog());
		FontPreview.load(loader).then(preview -> {
			loader.close();
			files.close();
			if (preview.text.width <= 0 || preview.text.glyphs.length == 0 || preview.atlas.pixels.length == 0)
				throw "font asset produced no text";
			Sys.println("PASS: content-addressed font asset loaded, decoded and prepared");
			hxn.Loop.exit(0);
		}, error -> {
			loader.close();
			files.close();
			Sys.stderr().writeString(Std.string(error) + "\n");
			hxn.Loop.exit(1);
		});
	}
}
