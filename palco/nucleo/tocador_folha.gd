class_name TocadorFolha
extends Node2D
## Le a folha do Atelie sem ResourceLoader/import e desenha apenas o quadro atual.

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
			indice = proximo
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
		draw_texture_rect_region(textura, Rect2(-ancora, origem.size), origem)
