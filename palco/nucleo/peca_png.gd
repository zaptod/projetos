class_name PecaPng
extends PecaPalco
## Uma peca feita de UM PNG do Atelie (palco/biblioteca/partes/<grupo>/...),
## montada pela Biblioteca quando o PNG existe no destino do manifesto
## (docs/sprites/CONTRATO_SLOTS.md). Nenhuma cena .tscn e gravada: a
## Biblioteca le o PNG, preenche os campos abaixo e empacota a peca na hora.
##
## Os gabaritos sao os do contrato (§1):
##   arma     1024x256: a mao na borda ESQUERDA, na altura do meio; a ponta na
##            borda direita. O palco estica ate o alcance real da hitbox
##            (`comprimento_ref` = distancia mao -> ponta, em px da imagem).
##   objeto   512x512: centro = centro do objeto, apontando para +x; a largura
##            da imagem = o diametro da hitbox (`r` da trilha).
##   evento   512x512 (KO 1024): centro = ponto do evento. Imagem parada: o
##            Godot faz o estouro (cresce, gira junto com o golpe e some).
##   camada   1024x1024: o gabarito do lutador (corpo de raio 256 no centro).
##
## O .json ao lado do PNG (o painel grava `tingir`, `origem`...) e lido se
## existir e nunca exigido. Campos que esta peca entende: `tingir`
## ("elemento" | "nenhum" | "#RRGGBB"), `empunhadura` e `ponta` ([x, y] na
## imagem, so arma), `tamanho_m` e `duracao_s` (so evento).

## "arma" | "objeto" | "evento" | "camada"
@export var modo := "objeto"
@export var textura: Texture2D
## o PNG de onde a peca veio (relatorio e testes)
@export var origem_png := ""
## "" | "elemento" | "#RRGGBB"
@export var tingir := ""
## arma: pontos na imagem (px). (-1, -1) = o gabarito (borda esquerda/direita, meio)
@export var empunhadura := Vector2(-1, -1)
@export var ponta := Vector2(-1, -1)
## objeto: gira com o angulo da trilha (projetil, summon); area/trap nao giram
@export var girar := true
## evento: largura no mundo (m) e vida (s de jogo)
@export var tamanho_m := 1.6
@export var duracao_s := 0.35

var _cor := Color.WHITE
var _r := 0.0
var _largura_m := 0.0
var _ang := 0.0
var _alfa := 1.0
var _evento := false
var idade := 0.0


func _tamanho() -> Vector2:
	return Vector2(textura.get_width(), textura.get_height()) if textura != null else Vector2(100, 100)


func _ready() -> void:
	# as pecas do Atelie sao desenhadas grandes (256 a 1024 px) e aparecem com
	# 20 a 200 px: sem mipmap a reducao serrilha
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS


## A geometria do gabarito: a Biblioteca chama ANTES de empacotar, para o
## palco ja achar `comprimento_ref` (arma) e `raio_ref` (camada) na peca.
func preparar() -> void:
	# a textura vem pre-multiplicada da Biblioteca (sem franja escura)
	var mistura := CanvasItemMaterial.new()
	mistura.blend_mode = CanvasItemMaterial.BLEND_MODE_PREMULT_ALPHA
	material = mistura
	if modo == "arma":
		var t := _tamanho()
		if empunhadura.x < 0.0:
			empunhadura = Vector2(0.0, t.y * 0.5)
		if ponta.x < 0.0:
			ponta = Vector2(t.x, t.y * 0.5)
		comprimento_ref = maxf(1.0, empunhadura.distance_to(ponta))
	elif modo == "camada":
		# corpo de raio 256 no gabarito 1024: o lutador escala por raio_px / raio_ref
		raio_ref = _tamanho().x * 0.25


## O numero do campo, ou `padrao`. O cabecalho de uma TRILHA (projetil,
## summon, orbe...) traz os CANAIS no mesmo dicionario, como listas
## (`ang`, `r`, `x`...): float() de uma lista e SCRIPT ERROR e o configurar
## abortava antes do raio (a invocacao saia com 57% do tamanho).
static func _numero(dados: Dictionary, campo: String, padrao: float) -> float:
	var v = dados.get(campo)
	return float(v) if typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT else padrao


## Quanto o tingido clareia a cor do elemento: multiplicar pela cor pura
## escurece demais nos elementos escuros (Trevas 0x640096, Void).
const CLAREAR_TINGIDO := 0.3


func configurar(dados: Dictionary, _ctx: Dictionary) -> void:
	if tingir == "elemento":
		var elemento := str(dados.get("elemento", "")).to_upper()
		if elemento != "" and elemento != "DEFAULT" and UtilPalco.PALETAS.has(elemento):
			var mid = UtilPalco.paleta(elemento).get("mid")
			_cor = (UtilPalco.cor(mid[0]) if typeof(mid) == TYPE_ARRAY else Color.WHITE).lightened(CLAREAR_TINGIDO)
		elif typeof(dados.get("cor")) == TYPE_INT or typeof(dados.get("cor")) == TYPE_FLOAT:
			# sem elemento: a cor do proprio objeto (o Espirito e lilas)
			_cor = UtilPalco.cor(dados["cor"]).lightened(CLAREAR_TINGIDO)
	elif tingir.begins_with("#"):
		_cor = Color(tingir)
	_ang = deg_to_rad(_numero(dados, "dir", _numero(dados, "ang", _numero(dados, "angulo", 0.0))))
	# objeto sem raio na amostra: o raio fixo da trilha (summon) ou a largura (trap)
	if _numero(dados, "raio", 0.0) > 0.0:
		_largura_m = 2.0 * _numero(dados, "raio", 0.0)
	elif _numero(dados, "largura", 0.0) > 0.0:
		_largura_m = _numero(dados, "largura", 0.0)


func atualizar(amostra: Dictionary, ctx: Dictionary) -> void:
	if modo == "evento":
		_evento = true
		idade += float(ctx.get("dt_mundo", 1.0 / 30.0))
		if idade >= duracao_s:
			queue_free()
			return
	elif modo == "objeto":
		_r = _numero(amostra, "r", _r)
		_ang = deg_to_rad(_numero(amostra, "ang", rad_to_deg(_ang)))
		# area: aviso (ativ 0) mais apagado que o dano
		_alfa = 0.55 if _numero(amostra, "ativ", 1.0) < 0.5 else 1.0
	queue_redraw()


## A cor de tingir/apagar na mistura pre-multiplicada: o rgb tambem cai com
## o alfa (senao o apagar viraria brilho somado).
static func _pre(c: Color) -> Color:
	return Color(c.r * c.a, c.g * c.a, c.b * c.a, c.a)


func _draw() -> void:
	if textura == null:
		return
	var t := _tamanho()
	match modo:
		"arma":
			# a mao na origem, a ponta em +x (o palco gira e estica a raiz)
			var giro := -(ponta - empunhadura).angle()
			draw_set_transform(Vector2.ZERO, giro)
			draw_texture_rect(textura, Rect2(-empunhadura, t), false, _pre(_cor))
		"camada":
			draw_texture_rect(textura, Rect2(-t * 0.5, t), false, _pre(_cor))
		"evento":
			var vida := clampf(idade / maxf(0.01, duracao_s), 0.0, 1.0)
			var cresce := lerpf(0.7, 1.15, 1.0 - pow(1.0 - vida, 2.0))
			var cor := _cor
			cor.a *= clampf((1.0 - vida) / 0.5, 0.0, 1.0)
			var esc := tamanho_m * UtilPalco.PX_POR_M / t.x * cresce
			draw_set_transform(Vector2.ZERO, _ang, Vector2(esc, esc))
			draw_texture_rect(textura, Rect2(-t * 0.5, t), false, _pre(cor))
		_:
			var largura := 2.0 * _r if _r > 0.0 else (_largura_m if _largura_m > 0.0 else 1.0)
			var esc := largura * UtilPalco.PX_POR_M / t.x
			var cor := _cor
			cor.a *= _alfa
			draw_set_transform(Vector2.ZERO, _ang if girar else 0.0, Vector2(esc, esc))
			draw_texture_rect(textura, Rect2(-t * 0.5, t), false, _pre(cor))
	draw_set_transform(Vector2.ZERO)
