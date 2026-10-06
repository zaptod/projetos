extends SceneTree
## Lado Godot do teste de paridade do guarda-roupa (test_sorteio_variantes.py):
## resolve cada caso com o MESMO PartesLutador.resolver do palco, contra uma
## biblioteca temporaria, e grava a escolha (nivel, variante, estado, arquivo).
##
## godot --headless --path palco --script res://testes/sorteio_variantes.gd -- \
##   --casos=<casos.json> --saida=<escolhas.json>
##
## casos.json = {"biblioteca": "E:/tmp/bib", "casos": [[personagem, classe, parte, expressao], ...]}

func _initialize() -> void:
	var entrada := ""
	var saida := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--casos="):
			entrada = arg.substr(8)
		elif arg.begins_with("--saida="):
			saida = arg.substr(8)
	var json := JSON.new()
	if entrada == "" or saida == "" or json.parse(FileAccess.get_file_as_string(entrada)) != OK:
		printerr("[sorteio] uso: --casos=<json> --saida=<json>")
		quit(2)
		return
	var dados: Dictionary = json.data
	var biblioteca := str(dados.get("biblioteca", "")).replace("\\", "/").rstrip("/")
	PartesLutador.configurar_biblioteca(biblioteca)
	var escolhas := []
	var inicio := Time.get_ticks_usec()
	for caso in dados.get("casos", []):
		var achado := PartesLutador.resolver(str(caso[2]), str(caso[0]), str(caso[1]), str(caso[3]))
		if achado.is_empty():
			escolhas.append(null)
			continue
		escolhas.append({"nivel": achado.get("nivel"), "variante": achado.get("variante"),
			"estado": achado.get("estado"),
			"arquivo": str(achado.get("caminho", "")).trim_prefix(biblioteca + "/")})
	var gasto_ms := (Time.get_ticks_usec() - inicio) / 1000.0
	var arquivo := FileAccess.open(saida, FileAccess.WRITE)
	arquivo.store_string(JSON.stringify({"escolhas": escolhas, "ms": gasto_ms}))
	arquivo.close()
	print("[sorteio] %d casos em %.0f ms" % [escolhas.size(), gasto_ms])
	quit(0)
