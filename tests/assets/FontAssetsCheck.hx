import haxe.Exception;
import haxe.io.Bytes;
import hxn.Future;
import hxn.assets.AssetLoader;
import hxn.assets.AssetSource;
import hxn.text.Font;
import hxn.text.FontAssets;
import hxn.text.FontOptions;
import hxn.text.TextException;

class FontAssetsCheck {
	static function require(value:Bool, message:String):Void {
		if (!value)
			throw message;
	}

	static function fails(operation:() -> Void, expected:String):Void {
		var message = "";
		try
			operation()
		catch (error:Exception)
			message = error.message;
		require(message.indexOf(expected) >= 0, 'expected $expected, got $message');
	}

	static function main():Void {
		final bytes = haxe.Resource.getBytes("latin");
		final info = GameAssets.catalog().get(GameAssets.addresses.Ui);
		require(info.contentId == "sha256:" + haxe.crypto.Sha256.make(bytes).toHex(), "generated font content identity");
		require(info.mediaType == "font/ttf" && info.dynamicAsset, "font catalog metadata");
		fails(() -> {
			GameAssets.Ui.family();
		}, "not loaded");
		final source = new BytesSource(bytes);
		final loader = new AssetLoader(source, GameAssets.catalog());
		final preview = FontPreview.load(loader).await();
		require(preview.text.width > 0 && preview.text.glyphs.length > 0, "example font measurements");
		require(preview.atlas.full && preview.atlas.pixels.length > 0, "owned example atlas snapshot");
		fails(() -> {
			GameAssets.Ui.family();
		}, "not loaded");
		final first = FontAssets.load(loader, GameAssets.addresses.Ui).await();
		final second = FontAssets.load(loader, GameAssets.addresses.Ui).await();
		require(source.reads == 1 && !first.same(second), "share cached bytes, own separate fonts");
		first.close();
		loader.unload(GameAssets.addresses.Ui);
		loader.close();
		require(second.shape("office", 24).width > 0, "font survives cache eviction and source close");
		second.close();
		final corrupt = new AssetLoader(new BytesSource(Bytes.ofString("changed")), GameAssets.catalog());
		fails(() -> {
			FontAssets.load(corrupt, GameAssets.addresses.Ui).await();
		}, "content digest");
		corrupt.close();
		final rejected = new AssetLoader(new FailureSource(), GameAssets.catalog());
		fails(() -> {
			FontAssets.load(rejected, GameAssets.addresses.Ui).await();
		}, "source unavailable");
		rejected.close();
		final invalid = new AssetLoader(new BytesSource(Bytes.ofString("not a font")), TestFonts.catalog());
		var typed = false;
		try
			FontAssets.load(invalid, TestFonts.addresses.Invalid).await()
		catch (error:TextException)
			typed = error.error != null;
		require(typed, "decoder failures remain typed rejected futures");
		invalid.close();
		final deferred = new DeferredSource();
		final variable = new AssetLoader(deferred, TestFonts.catalog());
		final options:FontOptions = {weight: 700};
		final pending = FontAssets.load(variable, TestFonts.addresses.Variable, options);
		require(!pending.isReady(), "loading remains asynchronous");
		options.weight = 400;
		deferred.complete(haxe.Resource.getBytes("arabic"));
		final bold = pending.await();
		final expected = FontAssets.decode(haxe.Resource.getBytes("arabic"), {weight: 700});
		final regular = FontAssets.decode(haxe.Resource.getBytes("arabic"), {weight: 400});
		require(expected.shape("مرحبا", 24).width != regular.shape("مرحبا", 24).width, "weight fixture must distinguish selections");
		regular.close();
		require(bold.shape("مرحبا", 24).width == expected.shape("مرحبا", 24).width, "snapshot variable-font options before delivery");
		bold.close();
		expected.close();
		variable.close();
		Sys.println("PASS: annotated font assets, content verification, async decoding and ownership");
		final nonce = haxe.Resource.getString("hxn-text-test-nonce");
		if (nonce != null)
			Sys.println("hxn-text-test:" + nonce);
		hxn.Loop.exit(0);
	}
}

@:build(hxn.assets.Assets.build())
private class TestFonts {
	@:asset("variable", "arabic.ttf") @:dynamicAsset @:contentAddressed @:assetDecode(FontAssets.decode)
	public static var Variable:Font;
	@:asset("invalid", "runtime/invalid.font") @:dynamicAsset @:assetDecode(FontAssets.decode)
	public static var Invalid:Font;
}

private class BytesSource implements AssetSource {
	final bytes:Bytes;

	public var reads(default, null) = 0;

	public function new(bytes:Bytes)
		this.bytes = bytes;

	public function read(path:String):Future<Bytes> {
		reads++;
		return Future.resolved(bytes);
	}
}

private class FailureSource implements AssetSource {
	public function new() {}

	public function read(path:String):Future<Bytes>
		return Future.rejected(new Exception("source unavailable"));
}

private class DeferredSource implements AssetSource {
	final pending = new Future<Bytes>();

	public function new() {}

	public function read(path:String):Future<Bytes>
		return pending;

	public function complete(bytes:Bytes):Void {
		@:privateAccess pending.settle(bytes, null);
	}
}
