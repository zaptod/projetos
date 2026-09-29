extends PecaPalco
## FOLHA DE SPRITE ANIMADA: uma peca de efeito feita de uma folha (grade de
## quadros do mesmo tamanho), sem codigo. E o formato que a Oficina de
## sprites exporta (docs/palco/COMO-EDITAR.md, secao "Folha de sprite").
##
## A cena e so este script com os campos abaixo, salva com o NOME que a
## biblioteca procura (efeitos/skills/<skill>.tscn,
## efeitos/objetos/<tipo>/<elemento>.tscn, efeitos/eventos/<tipo>[_<tier>].tscn).
## O mesmo arquivo serve de OBJETO (projetil, orbe, area, beam: o palco chama
## atualizar() com a amostra da trilha, e a peca segue o raio e o angulo da
## hitbox) e de EVENTO (acerto, ko...: atualizar() vem com amostra vazia, a
## peca toca e se apaga sozinha).
##
## O relogio e o do JOGO (ctx.dt_mundo): congela no hitstop, anda devagar no
## slow-mo, e o mesmo quadro sai igual em qualquer render.

@export_group("Folha")
## a imagem: quadros da esquerda para a direita, de cima para baixo, todos do
## mesmo tamanho; RGBA com fundo transparente
@export var folha: Texture2D
@export_range(1, 64, 1) var colunas: int = 1
@export_range(1, 64, 1) var linhas: int = 1
## quantos quadros valem (os ultimos da grade podem estar vazios); 0 = todos
@export_range(0, 4096, 1) var quadros: int = 0
@export_range(1.0, 60.0, 0.5) var fps: float = 24.0
## true = repete (projetil, aura); false = toca uma vez (evento; num objeto,
## a animacao acompanha a vida dele: `prog` 0..1 escolhe o quadro)
@export var laco: bool = true

@export_group("Posicao e tamanho")
## o ponto do QUADRO (px, a partir do canto de cima a esquerda) que vai na
## posicao da peca: o centro do projetil, o pe da explosao. (-1, -1) = centro
@export var ancora: Vector2 = Vector2(-1, -1)
## a folha desenha o objeto apontando para a DIREITA (+x); true = gira com o
## angulo do objeto (ou a direcao do golpe, no evento)
@export var girar: bool = true
## largura do QUADRO no mundo, em metros (100 px = 1 m), quando nao ha raio
@export_range(0.05, 20.0, 0.05) var tamanho_m: float = 1.0
## > 0: a largura do quadro = escala_raio x o DIAMETRO da hitbox (objetos com
## raio `r`): o que acerta e o que aparece
@export_range(0.0, 20.0, 0.05) var escala_raio: float = 0.0

@export_group("Cor e vida")
## luz somada (fogo, energia) em vez de tinta normal
@export var aditivo: bool = false
## "" = as cores da folha; "elemento" = multiplica pela cor do elemento
## (UtilPalco.PALETAS, meio-tom); "#RRGGBB" = uma cor fixa
@export var tingir: String = ""
## evento: quanto tempo a peca vive (s de jogo); 0 = uma volta da folha
@export_range(0.0, 10.0, 0.05) var duracao_s: float = 0.0
## segundos finais em que a peca some (alfa ate 0)
@export_range(0.0, 2.0, 0.05) var sumir_s: float = 0.1

var idade := 0.0
var _evento := false
var _dados: Dictionary = {}
var _r := 0.0
var _ang := 0.0
var _prog := -1.0
var _cor := Color.WHITE


func _n() -> int:
	return quadros if quadros > 0 else colunas * linhas


func _vida() -> float:
	return duracao_s if duracao_s > 0.0 else _n() / maxf(1.0, fps)


func configurar(dados: Dictionary, _ctx: Dictionary) -> void:
	_dados = dados
	if aditivo:
		var mat := CanvasItemMaterial.new()
		mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		material = mat
	if tingir == "elemento":
		var mid = UtilPalco.paleta(str(dados.get("elemento", ""))).get("mid")
		_cor = UtilPalco.cor(mid[0]) if typeof(mid) == TYPE_ARRAY else Color.WHITE
	elif tingir.begins_with("#"):
		_cor = Color(tingir)
	_ang = deg_to_rad(float(dados.get("dir", dados.get("ang", 0.0))))


func atualizar(amostra: Dictionary, ctx: Dictionary) -> void:
	_evento = amostra.is_empty()
	idade += float(ctx.get("dt_mundo", 1.0 / 30.0))
	if _evento:
		if idade >= _vida():
			queue_free()
			return
	else:
		_r = float(amostra.get("r", _r))
		_ang = deg_to_rad(float(amostra.get("ang", rad_to_deg(_ang))))
		_prog = float(amostra.get("prog", -1.0))
	queue_redraw()


func _draw() -> void:
	if folha == null:
		return
	var n := _n()
	var k := int(floor(idade * fps))
	if laco:
		k = posmod(k, n)
	elif not _evento and _prog >= 0.0:
		k = int(_prog * n)
	k = clampi(k, 0, n - 1)
	var cel := Vector2(folha.get_width() / float(colunas), folha.get_height() / float(linhas))
	var origem := Rect2(Vector2((k % colunas) * cel.x, (k / colunas) * cel.y), cel)
	var largura := tamanho_m * UtilPalco.PX_POR_M
	if escala_raio > 0.0 and _r > 0.0:
		largura = escala_raio * 2.0 * _r * UtilPalco.PX_POR_M
	var esc := largura / cel.x
	var a := ancora if ancora.x >= 0.0 else cel / 2.0
	var cor := _cor
	if _evento and sumir_s > 0.0:
		cor.a *= clampf((_vida() - idade) / sumir_s, 0.0, 1.0)
	draw_set_transform(Vector2.ZERO, _ang if girar else 0.0, Vector2(esc, esc))
	draw_texture_rect_region(folha, Rect2(-a, cel), origem, cor)
	draw_set_transform(Vector2.ZERO)
