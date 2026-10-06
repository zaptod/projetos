extends Node2D
## Folha do "Ver no Godot": as seis familias de expressao do lutador montado
## com as pecas modulares, em 2 colunas x 3 linhas (1080x1920, retrato), para
## ler no celular sem dar zoom. Cada bolinha tem 340 px de diametro.
##
## godot --path palco res://ferramentas/previa_sprites.tscn -- \
##   --classe=berserker_furia --personagem= --saida=E:/tmp/previa.png
##   [--biblioteca=E:/tmp/bib]   biblioteca isolada (manifesto + partes/)
##   [--z=0.6 --esc_x=1.25 --esc_y=0.8 --ang=30]   pose (testes do pulo/squash)
##
## O layout (centros, raio) esta em docs/sprites/CONTRATO_SLOTS.md, "Previa".

const REPRESENTANTES := ["neutro", "furia", "animado", "panico", "dor", "morto"]
const NOMES := {"neutro": "Neutro", "furia": "Fúria", "animado": "Animado", "panico": "Pânico",
	"dor": "Dor", "morto": "Morto"}
const CORES := [0xD86565, 0xBD78E8, 0x5DBB8A, 0x6D9BE8, 0xE8B35F, 0xDC7AA3]
const COLUNAS := 2
const LARG_CELULA := 540.0
const ALT_CELULA := 576.0
const TOPO := 190.0          # faixa do titulo
const CENTRO_Y := 330.0      # do topo da celula ao centro da bolinha
const RAIO_M := 1.7          # 170 px de raio: bolinha de 340 px

var args := {}
var nomes := []


## Centro da bolinha (z = 0) da celula k; o teste Python usa as mesmas contas.
static func centro_celula(k: int) -> Vector2:
	return Vector2((k % COLUNAS + 0.5) * LARG_CELULA, TOPO + (k / COLUNAS) * ALT_CELULA + CENTRO_Y)


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--") and "=" in arg:
			args[arg.substr(2, arg.find("=") - 2)] = arg.substr(arg.find("=") + 1)
	RenderingServer.set_default_clear_color(Color8(25, 29, 39))
	var estilo := load("res://biblioteca/estilo.tres") as EstiloPalco
	var biblioteca := str(args.get("biblioteca", ""))
	if biblioteca != "":
		PartesLutador.configurar_biblioteca(biblioteca)
	var cena := load("res://biblioteca/lutadores/_padrao.tscn") as PackedScene
	var classe := str(args.get("classe", ""))
	var personagem := str(args.get("personagem", ""))
	for k in REPRESENTANTES.size():
		var no := cena.instantiate()
		no.position = centro_celula(k)
		add_child(no)
		no.configurar({"slot": "p1", "nome": personagem, "classe": classe, "cor": CORES[k], "raio_corpo": RAIO_M},
			{"estilo": estilo, "zoom": 1.0, "t_jogo": 1.0, "quadro": 0})
		no.atualizar({"expr": RostoPalco.EXPRESSOES.find(REPRESENTANTES[k]), "ang": float(args.get("ang", 0.0)),
			"esc_x": float(args.get("esc_x", 1.0)), "esc_y": float(args.get("esc_y", 1.0)),
			"z": float(args.get("z", 0.0)), "flags": 0, "flash": 0.0},
			{"estilo": estilo, "zoom": 1.0, "t_jogo": 1.0, "quadro": 0})
		nomes.append(REPRESENTANTES[k])
	call_deferred("_salvar")


## "Berserker (Fúria)", "Celeste a Impiedosa  ·  Berserker (Fúria)" ou
## "Comum (todos os lutadores)": nunca o id.
func _titulo() -> String:
	var classe := str(args.get("classe", ""))
	var personagem := str(args.get("personagem", ""))
	var nome_classe := ""
	if classe != "":
		nome_classe = PartesLutador.rotulo("classe", classe)
		if nome_classe == "":
			nome_classe = classe.replace("_", " ").capitalize()
	if personagem != "":
		return personagem + ("  ·  " + nome_classe if nome_classe != "" else "")
	return nome_classe if nome_classe != "" else "Comum (todos os lutadores)"


func _draw() -> void:
	var fonte := ThemeDB.fallback_font
	draw_string(fonte, Vector2(0, 72), "Prévia no Godot", HORIZONTAL_ALIGNMENT_CENTER, 1080, 40, Color(0.70, 0.75, 0.84))
	draw_string(fonte, Vector2(0, 150), _titulo(), HORIZONTAL_ALIGNMENT_CENTER, 1080, 60, Color.WHITE)
	for k in nomes.size():
		var c := centro_celula(k)
		draw_string(fonte, Vector2(c.x - LARG_CELULA / 2.0, c.y - CENTRO_Y + 70), str(NOMES.get(nomes[k], nomes[k])),
			HORIZONTAL_ALIGNMENT_CENTER, LARG_CELULA, 50, Color(0.86, 0.89, 0.95))


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
