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
var escala_json := 1.0
var espelho_json := false
var rotacao_json := 0.0
var indice := 0
var sentido := 1
var decorrido := 0.0
var gatilho_animacao := ""
var _animacoes := {}
var _ocioso := ""
var _terminou := false
## Gatilhos que o palco manda A CADA QUADRO (canais da amostra). Enquanto uma
## animacao de EVENTO sem loop toca (`_travado`), eles nao a cortam: antes o
## `ocioso`/`golpe_fase` da arma trocava o `projetil_fim` no quadro seguinte
## e o evento durava 1 quadro de video (GOD-3).
const GATILHOS_DE_QUADRO := ["ocioso", "golpe_fase", "expr"]
var _travado := false
## Animacoes por ESTADO do catalogo (o rosto: os 24 estados sao as 24
## expressoes, todos com os mesmos gatilhos). `_animacoes` e a do estado ativo:
## a base (todas as animacoes, como sempre) com as do estado por cima.
var _base := {}
var _por_estado := {}
var estado_atual := ""
## carinha pedida que nao esta desenhada -> a usada no lugar (vai ao relatorio)
var herdado := {}
## Expressao -> familia (docs/sprites/slots_exemplo.json `familias_expressao`).
## Carinha que nao esta desenhada usa a mais parecida: a familia, depois a
## neutra, depois qualquer uma desenhada (Grimorio builds/boca-de-uma-carinha).
const FAMILIA_EXPRESSAO := {"neutro": "neutro", "focado": "neutro", "glacial": "neutro",
	"concentrado": "neutro", "firmeza": "neutro", "tedio": "neutro", "furia": "furia",
	"determinado": "furia", "berserk": "furia", "esforco": "furia", "limite": "furia",
	"animado": "animado", "confiante": "animado", "euforico": "animado", "extase": "animado",
	"panico": "panico", "nervoso": "panico", "desespero": "panico", "alerta": "panico",
	"confuso": "panico", "dor": "dor", "tonto": "dor", "tristeza": "dor", "morto": "morto"}
## Tamanho no palco = regra do Atelie (`atelie_animacoes.montagem`): o maior
## lado do quadro vira `tamanho_padrao` corpos (1,0 = o diametro do lutador);
## a `escala` do animacao.json multiplica por cima. Sem corpo informado: 1:1.
var corpo_px := 0.0
var tamanho_rel := 1.0
var segue_animacao := ""


func _ready() -> void:
	if not catalogo_peca.is_empty():
		_preparar_catalogo()


## A configuracao e exportada antes de empacotar a cena. Assim, ao contrario
## do antigo `carregar` antes de `pack()`, ela continua no no instanciado.
func _preparar_catalogo() -> void:
	_base.clear()
	_por_estado.clear()
	for estado in catalogo_peca.get("estados", []):
		var id_estado := str(estado.get("id", ""))
		for animacao in estado.get("animacoes", []):
			var chave := str(animacao.get("gatilho", ""))
			if chave == "":
				continue
			var pasta := str(animacao.get("pasta", ""))
			if pasta != "":
				var dado := {"pasta": pasta, "loop": bool(animacao.get("loop", true)),
					"tamanho": _tamanho_do_catalogo(animacao.get("tamanho_padrao", "1")),
					"segue": str(animacao.get("segue", "lutador")), "camada": int(animacao.get("camada", 0))}
				_base[chave] = dado
				if not _por_estado.has(id_estado):
					_por_estado[id_estado] = {}
				_por_estado[id_estado][chave] = dado
	_animacoes = _base.duplicate()
	# Peca de expressoes (o rosto) comeca no 1o estado desenhado pela ordem do
	# catalogo (o `neutro`, quando ha); a base sozinha seria a ULTIMA carinha.
	if _tem_expressoes():
		_aplicar_estado(_resolver_estado("neutro"))
	_definir_ocioso()
	if _ocioso != "":
		_trocar(_ocioso)


## A animacao de repouso e a `ocioso`; peca sem ela (ex. Cristais Flutuantes:
## so `orbitar`, gatilho orbe) repousa na 1a que tem folha — antes ela nunca
## tocava (08/10/2026).
func _definir_ocioso() -> void:
	_ocioso = ""
	if _animacoes.has("ocioso"):
		_ocioso = "ocioso"
	elif not _animacoes.is_empty():
		_ocioso = str(_animacoes.keys()[0])


func _tem_expressoes() -> bool:
	for id_estado in _por_estado:
		if FAMILIA_EXPRESSAO.has(id_estado):
			return true
	return false


## O estado desenhado mais parecido com `nome`: ele, a familia, a neutra, a
## 1a desenhada (nunca some, nunca mistura com a provisoria).
func _resolver_estado(nome: String) -> String:
	for candidato in [nome, str(FAMILIA_EXPRESSAO.get(nome, "")), "neutro"]:
		if candidato != "" and _por_estado.has(candidato):
			return candidato
	for id_estado in catalogo_peca.get("estados", []):
		if _por_estado.has(str(id_estado.get("id", ""))):
			return str(id_estado.get("id", ""))
	return ""


func _aplicar_estado(id_estado: String) -> void:
	estado_atual = id_estado
	_animacoes = _base.duplicate()
	_animacoes.merge(_por_estado.get(id_estado, {}), true)


## Troca o estado (a expressao do rosto). So recomeca a animacao quando a
## folha muda, e mesmo assim no MESMO quadro: a carinha troca sem o grito
## voltar ao comeco. Peca sem estados de expressao ignora; repassa aos filhos.
func estado(nome: String) -> void:
	if _tem_expressoes():
		var alvo := _resolver_estado(nome)
		if nome != "" and alvo != "" and alvo != nome:
			herdado[nome] = alvo
		if alvo != "" and alvo != estado_atual:
			var pasta_antes := str(_animacoes.get(gatilho_animacao, {}).get("pasta", ""))
			_aplicar_estado(alvo)
			_definir_ocioso()
			var dado: Dictionary = _animacoes.get(gatilho_animacao, {})
			if gatilho_animacao != "" and not dado.is_empty() and str(dado.get("pasta", "")) != pasta_antes:
				var guardado := [indice, sentido, decorrido, _terminou]
				_trocar(gatilho_animacao)
				if gatilho_animacao != "" and not quadros.is_empty():
					indice = mini(int(guardado[0]), quadros.size() - 1)
					sentido = int(guardado[1])
					decorrido = float(guardado[2])
					_terminou = bool(guardado[3])
				queue_redraw()
	for filho in get_children():
		if filho.has_method("estado"):
			filho.estado(nome)


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
	fps = float(dados.get("fps", 12.0))
	if fps <= 0.0:
		push_warning("[palco] fps invalido na folha, usando 12")
		fps = 12.0
	loop = bool(dados.get("loop", true))
	ida_e_volta = bool(dados.get("ida_e_volta", false))
	duracoes = dados.get("duracao_por_quadro", {}) if typeof(dados.get("duracao_por_quadro")) == TYPE_DICTIONARY else {}
	var a = dados.get("ancora", {})
	ancora = Vector2(float(a.get("x", 0.0)), float(a.get("y", 0.0))) if typeof(a) == TYPE_DICTIONARY else Vector2.ZERO
	escala_json = float(dados.get("escala", 1.0))
	espelho_json = bool(dados.get("espelho", false))
	rotacao_json = float(dados.get("rotacao", 0.0))
	var tamanho_folha := textura.get_size()
	for q in quadros:
		if typeof(q) != TYPE_DICTIONARY or float(q.get("x", -1)) < 0.0 or float(q.get("y", -1)) < 0.0 \
				or float(q.get("w", 0)) <= 0.0 or float(q.get("h", 0)) <= 0.0 \
				or float(q.get("x", 0)) + float(q.get("w", 0)) > tamanho_folha.x \
				or float(q.get("y", 0)) + float(q.get("h", 0)) > tamanho_folha.y:
			push_warning("[palco] quadro fora da folha: " + pasta)
			quadros = []
			return false
	gatilho_animacao = str(dados.get("gatilho", ""))
	queue_redraw()
	return not quadros.is_empty()


func tocar(novo_gatilho: String) -> void:
	if not _animacoes.is_empty():
		var de_quadro := novo_gatilho in GATILHOS_DE_QUADRO
		if de_quadro and _travado:
			return                       # o evento toca ate o fim (GOD-3)
		if novo_gatilho == "ocioso" and not _animacoes.has("ocioso"):
			novo_gatilho = _ocioso       # "voltar ao repouso" na peca sem ocioso
		# chamado a cada quadro: so troca (e recomeca) quando muda de animacao
		if _animacoes.has(novo_gatilho) and novo_gatilho != gatilho_animacao:
			_trocar(novo_gatilho)
			_travado = not de_quadro and gatilho_animacao == novo_gatilho and not loop
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
	for filho in get_children():
		if filho.has_method("gatilho"):
			filho.gatilho(novo_gatilho)


func avancar(delta: float) -> void:
	# os filhos (o rosto pendurado no lutador) andam junto: antes ficavam no
	# quadro 0 (GOD-1)
	for filho in get_children():
		if filho.has_method("avancar"):
			filho.avancar(delta)
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
	if _terminou:
		_travado = false                 # o evento acabou: o quadro volta a mandar
	if _terminou and not loop and _ocioso != "" and gatilho_animacao != _ocioso:
		_trocar(_ocioso)


func _trocar(novo_gatilho: String) -> void:
	var dado: Dictionary = _animacoes.get(novo_gatilho, {})
	if dado.is_empty() or not carregar(ProjectSettings.globalize_path(str(dado.get("pasta", "")))):
		return
	gatilho_animacao = novo_gatilho
	loop = bool(dado.get("loop", loop))
	tamanho_rel = float(dado.get("tamanho", 1.0))
	segue_animacao = str(dado.get("segue", "lutador"))
	z_index = int(dado.get("camada", 0))
	indice = 0
	sentido = 1
	decorrido = 0.0
	_terminou = false


## "1,0 do corpo" -> 1.0 (o catalogo escreve o numero em portugues)
static func _tamanho_do_catalogo(valor) -> float:
	var texto := str(valor).replace(",", ".").strip_edges().split(" ")[0]
	return float(texto) if texto.is_valid_float() and float(texto) > 0.0 else 1.0


func ajustar_corpo(diametro_px: float) -> void:
	if not is_equal_approx(corpo_px, diametro_px):
		corpo_px = diametro_px
		queue_redraw()
	# o rosto pendurado cresce com o corpo: antes ficava no tamanho nativo da
	# folha (GOD-1)
	for filho in get_children():
		if filho.has_method("ajustar_corpo"):
			filho.ajustar_corpo(diametro_px)


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
		var escala := fator * escala_json
		var escala_local := Vector2(-escala if espelho_json else escala, escala)
		draw_set_transform(Vector2.ZERO, deg_to_rad(rotacao_json), escala_local)
		# contrato (docs/sprites/ATELIE_NOVO.md): ancora RELATIVA ao quadro (0..1);
		# valor acima de 1 e de folha antiga, em pixels
		var ponto := ancora
		if absf(ancora.x) <= 1.0 and absf(ancora.y) <= 1.0:
			ponto = Vector2(ancora.x * origem.size.x, ancora.y * origem.size.y)
		draw_texture_rect_region(textura, Rect2(-ponto, origem.size), origem)
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
