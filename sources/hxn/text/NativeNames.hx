package hxn.text;

#if macro
import haxe.macro.Context;
import haxe.macro.Type;
#end

/** Keeps public Haxe names separate from hxn's existing C++ text helper. **/
@:noCompletion
class NativeNames {
	public static macro function register():haxe.macro.Expr {
		if (Context.defined("cpp"))
			Context.onAfterTyping(function(types:Array<ModuleType>) {
				for (type in types) {
					final base:haxe.macro.Type.BaseType = switch (type) {
						case TClassDecl(value): value.get();
						case TEnumDecl(value): value.get();
						case TAbstract(value): value.get();
						case TTypeDecl(value): value.get();
					};
					if (base.pack.join(".") == "hxn.text" && !base.meta.has(":native"))
						base.meta.add(":native", [macro $v{"hxn_text." + base.name}], base.pos);
				}
			});
		return macro null;
	}
}
