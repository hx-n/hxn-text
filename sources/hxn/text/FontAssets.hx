package hxn.text;

#if hxn_assets
import haxe.io.Bytes;
import hxn.Future;
import hxn.assets.AssetLoader;

/** Decodes font assets while leaving byte caching and transport with hxn-assets. */
class FontAssets {
	/** Runtime decoder for a typed @:dynamicAsset Font field. The caller owns the font. */
	public static function decode(bytes:Bytes, ?options:FontOptions):Font {
		return new Font(bytes, options == null ? {} : options);
	}

	/** Loads verified asset bytes and creates a new caller-owned font for this request. */
	public static function load(loader:AssetLoader, address:String, ?options:FontOptions):Future<Font> {
		// Snapshot the selection before asynchronous delivery can observe caller edits.
		final selected:FontOptions = options == null ? {} : {faceIndex: options.faceIndex, weight: options.weight};
		return loader.load(address).map(bytes -> decode(bytes, selected));
	}
}
#end
