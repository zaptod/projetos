extends SceneTree
## Uso pelo teste Python: confirma em pixels da folha que as DUAS pecas
## anexadas chegaram a tela: a pele vermelha (embaixo) e os olhos azuis (por
## cima). So o azul nao basta: um olho que cobre tudo esconderia uma pele que
## nunca foi desenhada.
##
## godot --headless --path palco --script res://testes/verificar_previa.gd -- \
##   --png=<folha.png> [--min=100]

func _initialize() -> void:
	var png := ""
	var minimo := 100
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--png="):
			png = arg.substr(6)
		elif arg.begins_with("--min="):
			minimo = int(arg.substr(6))
	var imagem := Image.load_from_file(png)
	var azul := 0
	var vermelho := 0
	var pos_azul := Vector2i(-1, -1)
	var pos_vermelho := Vector2i(-1, -1)
	if imagem != null:
		for y in range(0, imagem.get_height(), 8):
			for x in range(0, imagem.get_width(), 8):
				var cor := imagem.get_pixel(x, y)
				if cor.b > 0.8 and cor.r < 0.2 and cor.g < 0.2:
					azul += 1
					pos_azul = Vector2i(x, y)
				elif cor.r > 0.8 and cor.g < 0.2 and cor.b < 0.2:
					vermelho += 1
					pos_vermelho = Vector2i(x, y)
	var ok := azul > minimo and vermelho > minimo
	print("[previa-teste] tamanho=", imagem.get_size() if imagem != null else Vector2.ZERO,
		" azul=", azul, " em ", pos_azul, " vermelho=", vermelho, " em ", pos_vermelho, " ok=", ok)
	quit(0 if ok else 1)
