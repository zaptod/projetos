extends SceneTree
## Rasteriza um SVG numa escala qualquer (o ThorVG do proprio Godot) e grava
## PNG. Serve para recortar pecas vetoriais (o overview.svg do Kenney Shape
## Characters) nitidas no tamanho de uso, sem depender de Inkscape.
##
##   godot --headless --path palco --script res://ferramentas/rasterizar_svg.gd -- --svg=A.svg --png=B.png --escala=4

func _initialize() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.substr(2, a.find("=") - 2)] = a.substr(a.find("=") + 1)
	var texto := FileAccess.get_file_as_string(str(args.get("svg", "")))
	if texto.is_empty():
		printerr("rasterizar_svg: nao li ", args.get("svg"))
		quit(2)
		return
	var img := Image.new()
	var erro := img.load_svg_from_string(texto, float(args.get("escala", "1")))
	if erro != OK:
		printerr("rasterizar_svg: SVG invalido (%d)" % erro)
		quit(1)
		return
	erro = img.save_png(str(args.get("png", "")))
	print("rasterizar_svg: %s %s -> %s (%d)" % [args.get("svg"), img.get_size(), args.get("png"), erro])
	quit(0 if erro == OK else 1)
