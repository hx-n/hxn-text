class Host {
	static function main():Void {
		final arguments = Sys.args();
		if (arguments.length != 1)
			throw "expected one CPPIA script";
		cpp.cppia.Host.runFile(arguments[0]);
	}
}
