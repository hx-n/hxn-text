import hxn.Future;
import hxn.assets.AssetLoader;
import hxn.text.AtlasKind;
import hxn.text.AtlasUpdate;
import hxn.text.PreparedText;
import hxn.text.TextEngine;

typedef PreviewData = {
	var text:PreparedText;
	var atlas:AtlasUpdate;
}

/** A renderer can retain the returned geometry and pixel snapshot. */
class FontPreview {
	public static function load(loader:AssetLoader):Future<PreviewData> {
		return GameAssets.load(loader).map(_ -> {
			final font = GameAssets.Ui;
			final engine = new TextEngine();
			function release():Void {
				font.close();
				GameAssets.unload();
				engine.close();
			}
			try {
				final preview:PreviewData = {
					text: engine.prepare(font, "Hello, asset fonts!", {size: 24}),
					atlas: engine.atlas(AtlasKind.Coverage, 0)
				};
				release();
				return preview;
			} catch (error:haxe.Exception) {
				release();
				throw error;
			}
		});
	}
}
