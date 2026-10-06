extends SceneTree
## Uso pelo teste Python: confirma que a camada de olhos desenhada por ultimo
## venceu a pele em pixels da folha.

func _initialize() -> void:
	var png := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--png="):
			png = arg.substr(6)
	var imagem := Image.load_from_file(png)
	var azul := 0
	var pos := Vector2i.ZERO
	if imagem != null:
		for y in range(0, imagem.get_height(), 8):
			for x in range(0, imagem.get_width(), 8):
				var cor := imagem.get_pixel(x, y)
				if cor.b > 0.8 and cor.r < 0.2:
					azul += 1
					pos = Vector2i(x, y)
	var ok := azul > 100
	print("[previa-teste] tamanho=", imagem.get_size() if imagem != null else Vector2.ZERO, " azul=", azul, " pos=", pos, " ok=", ok)
	quit(0 if ok else 1)
