extends Node2D
## Folha rapida para o painel revisar as seis familias de expressao.
##
## godot --path palco res://ferramentas/previa_sprites.tscn -- \
##   --classe=berserker --personagem= --saida=E:/tmp/previa.png

const REPRESENTANTES := ["neutro", "furia", "animado", "panico", "dor", "morto"]
const CORES := [0xD86565, 0xBD78E8, 0x5DBB8A, 0x6D9BE8, 0xE8B35F, 0xDC7AA3]

var args := {}
var nomes := []


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--") and "=" in arg:
			args[arg.substr(2, arg.find("=") - 2)] = arg.substr(arg.find("=") + 1)
	RenderingServer.set_default_clear_color(Color8(25, 29, 39))
	var estilo := load("res://biblioteca/estilo.tres") as EstiloPalco
	var cena := load("res://biblioteca/lutadores/_padrao.tscn") as PackedScene
	var classe := str(args.get("classe", ""))
	var personagem := str(args.get("personagem", ""))
	for k in REPRESENTANTES.size():
		var no := cena.instantiate()
		var coluna := k % 3
		var linha := k / 3
		no.position = Vector2(180 + coluna * 360, 500 + linha * 800)
		add_child(no)
		no.configurar({"slot": "p1", "nome": personagem, "classe": classe, "cor": CORES[k], "raio_corpo": 1.45},
			{"estilo": estilo, "zoom": 1.0, "t_jogo": 1.0, "quadro": 0})
		no.atualizar({"expr": RostoPalco.EXPRESSOES.find(REPRESENTANTES[k]), "ang": 0.0, "esc_x": 1.0, "esc_y": 1.0,
			"z": 0.0, "flags": 0, "flash": 0.0}, {"estilo": estilo, "zoom": 1.0, "t_jogo": 1.0, "quadro": 0})
		nomes.append(REPRESENTANTES[k])
	call_deferred("_salvar")


func _draw() -> void:
	var fonte := ThemeDB.fallback_font
	draw_string(fonte, Vector2(48, 90), "PREVIA MODULAR  |  " + str(args.get("classe", "comum")), HORIZONTAL_ALIGNMENT_LEFT, -1, 42, Color.WHITE)
	for k in nomes.size():
		var coluna := k % 3
		var linha := k / 3
		draw_string(fonte, Vector2(70 + coluna * 360, 250 + linha * 800), str(nomes[k]).to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 30, Color(0.82, 0.86, 0.93))


func _salvar() -> void:
	# Dois frames garantem que as Textures dinamicas e os _draw dos lutadores
	# chegaram ao viewport inclusive no renderer de compatibilidade.
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var saida := str(args.get("saida", ""))
	if saida == "":
		printerr("[previa] falta --saida=<png>")
		get_tree().quit(2)
		return
	var erro := get_viewport().get_texture().get_image().save_png(saida)
	if erro != OK:
		printerr("[previa] nao gravou ", saida, " (", erro, ")")
		get_tree().quit(3)
		return
	print("[previa] ", saida, " (", REPRESENTANTES.size(), " expressoes)")
	get_tree().quit(0)
