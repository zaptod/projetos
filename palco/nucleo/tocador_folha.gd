class_name TocadorFolha
extends Node2D
## Le a folha do Atelie sem ResourceLoader/import e desenha apenas o quadro atual.

@export var catalogo_peca: Dictionary = {}
var textura: ImageTexture
var quadros: Array = []
var fps := 12.0
var loop := true
var ida_e_volta := false
var duracoes: Dictionary = {}
var ancora := Vector2.ZERO
var indice := 0
var sentido := 1
var decorrido := 0.0
var gatilho_animacao := ""
var _animacoes := {}
var _ocioso := ""
var _terminou := false
## Tamanho no palco = regra do Atelie (`atelie_animacoes.montagem`): o maior
## lado do quadro vira `tamanho_padrao` corpos (1,0 = o diametro do lutador);
## a `escala` do animacao.json multiplica por cima. Sem corpo informado: 1:1.
var corpo_px := 0.0
var tamanho_rel := 1.0


func _ready() -> void:
	if not catalogo_peca.is_empty():
		_preparar_catalogo()


## A configuracao e exportada antes de empacotar a cena. Assim, ao contrario
## do antigo `carregar` antes de `pack()`, ela continua no no instanciado.
func _preparar_catalogo() -> void:
	for estado in catalogo_peca.get("estados", []):
		for animacao in estado.get("animacoes", []):
			var chave := str(animacao.get("gatilho", ""))
			if chave == "":
				continue
			var pasta := str(animacao.get("pasta", ""))
			if pasta != "":
				_animacoes[chave] = {"pasta": pasta, "loop": bool(animacao.get("loop", true)),
					"tamanho": _tamanho_do_catalogo(animacao.get("tamanho_padrao", "1"))}
			if chave == "ocioso" and _ocioso == "":
				_ocioso = chave
	if _ocioso != "":
		_trocar(_ocioso)


func carregar(pasta: String) -> bool:
	var meta := pasta.path_join("animacao.json")
	var folha := pasta.path_join("folha.png")
	if not FileAccess.file_exists(meta) or not FileAccess.file_exists(folha):
		return false
	var dados = JSON.parse_string(FileAccess.get_file_as_string(meta))
	if typeof(dados) != TYPE_DICTIONARY or typeof(dados.get("quadros")) != TYPE_ARRAY:
		return false
	var imagem := Image.load_from_file(folha)
	if imagem == null or imagem.is_empty():
		return false
	textura = ImageTexture.create_from_image(imagem)
	quadros = dados["quadros"]
	fps = maxf(0.01, float(dados.get("fps", 12.0)))
	loop = bool(dados.get("loop", true))
	ida_e_volta = bool(dados.get("ida_e_volta", false))
	duracoes = dados.get("duracao_por_quadro", {}) if typeof(dados.get("duracao_por_quadro")) == TYPE_DICTIONARY else {}
	var a = dados.get("ancora", {})
	ancora = Vector2(float(a.get("x", 0.0)), float(a.get("y", 0.0))) if typeof(a) == TYPE_DICTIONARY else Vector2.ZERO
	scale = Vector2.ONE * float(dados.get("escala", 1.0))
	rotation_degrees = float(dados.get("rotacao", 0.0))
	if bool(dados.get("espelho", false)):
		scale.x = -absf(scale.x)
	gatilho_animacao = str(dados.get("gatilho", ""))
	queue_redraw()
	return not quadros.is_empty()


func tocar(novo_gatilho: String) -> void:
	if not _animacoes.is_empty():
		# chamado a cada quadro: so troca (e recomeca) quando muda de animacao
		if _animacoes.has(novo_gatilho) and novo_gatilho != gatilho_animacao:
			_trocar(novo_gatilho)
			indice = 0
			sentido = 1
			decorrido = 0.0
			queue_redraw()
		return
	if gatilho_animacao != "" and novo_gatilho != gatilho_animacao:
		return
	indice = 0
	sentido = 1
	decorrido = 0.0
	queue_redraw()


func gatilho(novo_gatilho: String) -> void:
	tocar(novo_gatilho)


func avancar(delta: float) -> void:
	if textura == null or quadros.is_empty():
		return
	decorrido += delta
	while decorrido >= _duracao_atual():
		decorrido -= _duracao_atual()
		var proximo := indice + sentido
		if proximo >= quadros.size() or proximo < 0:
			if ida_e_volta and quadros.size() > 1:
				sentido *= -1
				proximo = indice + sentido
			elif loop:
				proximo = 0
			else:
				proximo = indice
				_terminou = true
		indice = proximo
		queue_redraw()
		if _terminou:
			break
	if _terminou and not loop and _ocioso != "" and gatilho_animacao != _ocioso:
		_trocar(_ocioso)


func _trocar(novo_gatilho: String) -> void:
	var dado: Dictionary = _animacoes.get(novo_gatilho, {})
	if dado.is_empty() or not carregar(ProjectSettings.globalize_path(str(dado.get("pasta", "")))):
		return
	gatilho_animacao = novo_gatilho
	loop = bool(dado.get("loop", loop))
	tamanho_rel = float(dado.get("tamanho", 1.0))
	_terminou = false


## "1,0 do corpo" -> 1.0 (o catalogo escreve o numero em portugues)
static func _tamanho_do_catalogo(valor) -> float:
	var texto := str(valor).replace(",", ".").strip_edges().split(" ")[0]
	return float(texto) if texto.is_valid_float() and float(texto) > 0.0 else 1.0


func ajustar_corpo(diametro_px: float) -> void:
	if not is_equal_approx(corpo_px, diametro_px):
		corpo_px = diametro_px
		queue_redraw()


func _duracao_atual() -> float:
	return maxf(0.001, float(duracoes.get(str(indice), 1.0 / fps)))


func _draw() -> void:
	if textura == null or indice >= quadros.size():
		return
	var q = quadros[indice]
	if typeof(q) != TYPE_DICTIONARY:
		return
	var origem := Rect2(float(q.get("x", 0)), float(q.get("y", 0)), float(q.get("w", 0)), float(q.get("h", 0)))
	if origem.size.x > 0.0 and origem.size.y > 0.0:
		var fator := 1.0
		if corpo_px > 0.0:
			fator = corpo_px * tamanho_rel / maxf(origem.size.x, origem.size.y)
		draw_set_transform(Vector2.ZERO, 0.0, Vector2(fator, fator))
		draw_texture_rect_region(textura, Rect2(-ancora, origem.size), origem)
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
