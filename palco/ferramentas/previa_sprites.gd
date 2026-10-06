extends Node2D
## Folha do "Ver no Godot": as seis familias de expressao do lutador montado
## com as pecas modulares, em 2 colunas x 3 linhas (1080x1920, retrato), para
## ler no celular sem dar zoom. Cada bolinha tem 340 px de diametro.
##
## godot --path palco res://ferramentas/previa_sprites.tscn -- \
##   --classe=berserker_furia --personagem= --saida=E:/tmp/previa.png
##   [--biblioteca=E:/tmp/bib]   biblioteca isolada (manifesto + partes/)
##   [--cor=#RRGGBB]   a cor do personagem (senao, procurada no banco pelo nome)
##   [--z=0.6 --esc_x=1.25 --esc_y=0.8 --ang=30]   pose (testes do pulo/squash)
##
## Cor das bolinhas: a previa de UM personagem pinta as seis com a cor DELE (a
## pele tingida como na luta): `--cor`, ou o banco de personagens pelo slug do
## nome. Classe, comum ou personagem fora do banco: as CORES de exemplo, e o
## titulo diz "cores de exemplo".
##
## O layout (centros, raio, titulo) esta em docs/sprites/CONTRATO_SLOTS.md,
## "Previa".

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
const LARGURA_TITULO := 1000.0   # 40 px de margem de cada lado da folha de 1080
const EXEMPLO := "cores de exemplo"

var args := {}
var nomes := []
var cor_personagem := -1     # 0xRRGGBB; -1 = cores de exemplo


## Centro da bolinha (z = 0) da celula k; o teste Python usa as mesmas contas.
static func centro_celula(k: int) -> Vector2:
	return Vector2((k % COLUNAS + 0.5) * LARG_CELULA, TOPO + (k / COLUNAS) * ALT_CELULA + CENTRO_Y)


## "#2080F0", "2080F0", "0x2080F0" ou "32,128,240" -> 0x2080F0; -1 se nao der.
static func ler_cor(texto: String) -> int:
	var t := texto.strip_edges()
	if t == "":
		return -1
	if "," in t:
		var partes := t.split(",")
		if partes.size() != 3:
			return -1
		var v := 0
		for p in partes:
			if not p.strip_edges().is_valid_int():
				return -1
			v = (v << 8) | clampi(p.strip_edges().to_int(), 0, 255)
		return v
	t = t.trim_prefix("#").trim_prefix("0x").trim_prefix("0X")
	if t.length() != 6 or not t.is_valid_hex_number():
		return -1
	return t.hex_to_int()


## O banco que o jogo (e o servidor do app) le: o do runtime quando ele tem
## personagens.json E armas.json, senao o snapshot do pacote.
static func arquivo_do_banco() -> String:
	var runtime := OS.get_environment("NEURAL_FIGHTS_RUNTIME_DIR")
	if runtime == "":
		var base := OS.get_environment("LOCALAPPDATA")
		if base == "":
			base = OS.get_environment("APPDATA")
		runtime = base.path_join("neural-fights") if base != "" else ""
	runtime = runtime.replace("\\", "/")
	if runtime != "" and FileAccess.file_exists(runtime.path_join("personagens.json")) \
			and FileAccess.file_exists(runtime.path_join("armas.json")):
		return runtime.path_join("personagens.json")
	return ProjectSettings.globalize_path("res://").path_join("../neural_fights/data/personagens.json").simplify_path()


## A cor do personagem no banco (cor_r/g/b), procurado pelo slug do nome
## como o palco recebe da timeline; -1 quando nao esta la (so LEITURA).
static func cor_no_banco(personagem: String, arquivo: String = "") -> int:
	var caminho := arquivo if arquivo != "" else arquivo_do_banco()
	if not FileAccess.file_exists(caminho):
		return -1
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(caminho)) != OK or typeof(json.data) != TYPE_ARRAY:
		return -1
	var alvo := UtilPalco.slug(personagem)
	for p in json.data:
		if typeof(p) != TYPE_DICTIONARY or UtilPalco.slug(str(p.get("nome", ""))) != alvo:
			continue
		if not (p.has("cor_r") and p.has("cor_g") and p.has("cor_b")):
			return -1
		return (clampi(int(p["cor_r"]), 0, 255) << 16) | (clampi(int(p["cor_g"]), 0, 255) << 8) \
			| clampi(int(p["cor_b"]), 0, 255)
	return -1


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
	if personagem.strip_edges() != "":
		cor_personagem = ler_cor(str(args.get("cor", "")))
		if cor_personagem < 0:
			cor_personagem = cor_no_banco(personagem)
	for k in REPRESENTANTES.size():
		var no := cena.instantiate()
		no.position = centro_celula(k)
		add_child(no)
		var cor: int = cor_personagem if cor_personagem >= 0 else CORES[k]
		no.configurar({"slot": "p1", "nome": personagem, "classe": classe, "cor": cor, "raio_corpo": RAIO_M},
			{"estilo": estilo, "zoom": 1.0, "t_jogo": 1.0, "quadro": 0})
		no.atualizar({"expr": RostoPalco.EXPRESSOES.find(REPRESENTANTES[k]), "ang": float(args.get("ang", 0.0)),
			"esc_x": float(args.get("esc_x", 1.0)), "esc_y": float(args.get("esc_y", 1.0)),
			"z": float(args.get("z", 0.0)), "flags": 0, "flash": 0.0},
			{"estilo": estilo, "zoom": 1.0, "t_jogo": 1.0, "quadro": 0})
		nomes.append(REPRESENTANTES[k])
	call_deferred("_salvar")


## As duas linhas do titulo, nunca o id:
##   personagem: ["Celeste a Impiedosa", "Berserker (Fúria)"]
##   classe:     ["Berserker (Fúria)", "cores de exemplo"]
##   comum:      ["Comum (todos os lutadores)", "cores de exemplo"]
## Sem a cor do personagem (fora do banco e sem --cor), a segunda linha
## tambem avisa "cores de exemplo".
func _titulo() -> Array:
	var classe := str(args.get("classe", ""))
	var personagem := str(args.get("personagem", "")).strip_edges()
	var nome_classe := ""
	if classe != "":
		nome_classe = PartesLutador.rotulo("classe", classe)
		if nome_classe == "":
			nome_classe = classe.replace("_", " ").capitalize()
	if personagem != "":
		var abaixo := PackedStringArray()
		if nome_classe != "":
			abaixo.append(nome_classe)
		if cor_personagem < 0:
			abaixo.append(EXEMPLO)
		return [personagem, "  ·  ".join(abaixo)]
	return [nome_classe if nome_classe != "" else "Comum (todos os lutadores)", EXEMPLO]


## Desenha `texto` centrado na folha, reduzindo a fonte ate caber em
## LARGURA_TITULO (e, no limite, cortando com reticencias): nada encosta
## na borda nem sai cortado no meio de uma palavra sem aviso.
func _linha(fonte: Font, base_y: float, texto: String, tamanho: int, minimo: int, cor: Color) -> void:
	if texto == "":
		return
	var t := tamanho
	while t > minimo and fonte.get_string_size(texto, HORIZONTAL_ALIGNMENT_LEFT, -1, t).x > LARGURA_TITULO:
		t -= 2
	while texto.length() > 1 and fonte.get_string_size(texto, HORIZONTAL_ALIGNMENT_LEFT, -1, t).x > LARGURA_TITULO:
		texto = texto.substr(0, texto.length() - 2) + "…"
	draw_string(fonte, Vector2((1080.0 - LARGURA_TITULO) / 2.0, base_y), texto, HORIZONTAL_ALIGNMENT_CENTER,
		LARGURA_TITULO, t, cor)


func _draw() -> void:
	var fonte := ThemeDB.fallback_font
	var titulo := _titulo()
	_linha(fonte, 46, "Prévia no Godot", 32, 32, Color(0.70, 0.75, 0.84))
	_linha(fonte, 112, str(titulo[0]), 58, 30, Color.WHITE)
	_linha(fonte, 168, str(titulo[1]), 40, 26, Color(0.86, 0.89, 0.95))
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
	print("[previa] ", saida, " (", REPRESENTANTES.size(), " expressoes, ",
		("cor do personagem #%06X" % cor_personagem) if cor_personagem >= 0 else EXEMPLO, ")")
	get_tree().quit(0)
