import hxn.text.Font;
import hxn.text.FontAssets;

@:build(hxn.assets.Assets.build())
class GameAssets {
	@:asset("ui.font", "NotoSans-Regular.ttf")
	@:contentAddressed
	@:assetMediaType("font/ttf")
	@:dynamicAsset
	@:assetDecode(FontAssets.decode)
	public static var Ui:Font;
	@:asset("ui.font.license", "NotoSans-OFL.txt")
	@:assetMediaType("text/plain")
	public static var UiLicense:String;
}
