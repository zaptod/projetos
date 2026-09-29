extends PecaPalco
## HUD PADRAO do palco, feito para ler no CELULAR (16E): nome, vida e o
## PLANO de cada lutador no topo. Liga com `"hud": true` no job
## (`main.py palco render --hud`, e o `palco ab` e a vitrine ligam). No duelo
## publicado o HUD ainda e o da edicao em Python ate a 16G.
##
## Desenhado em px da TELA de referencia 1080x1920 (escala com a tela):
##   nome        50 px, negrito, contorno preto de 10 px (o nome sobre a
##               bolinha e 40): cabe "Isandro Lumeprego" em meia tela
##   vida        barra de 40 px com borda, cel de 2 tons na cor do lado e o
##               "fantasma" claro do dano que acabou de entrar, que escorre
##   plano       o rotulo do plano de luta (tabelas.planos: PRESSAO, ISCA,
##               PRA PAREDE...) em 36 px, com a barrinha do progresso
## Fica entre 5% e 13% da altura: acima fica a barra de status do celular e
## abaixo a luta. Vida baixa (< 25%) pisca.

const REF := Vector2(1080, 1920)

var nomes := ["", ""]
var cores := [Color.WHITE, Color.WHITE]
var hp: Array[float] = [1.0, 1.0]
var fantasma: Array[float] = [1.0, 1.0]
var plano := ["", ""]
var plano_p: Array[float] = [0.0, 0.0]
var tela := Vector2(1080, 1920)
var quadro := 0
var _planos: Array = []
var _fonte: Font


func configurar(dados: Dictionary, ctx: Dictionary) -> void:
	var lista: Array = dados.get("lutadores", [])
	for k in mini(2, lista.size()):
		nomes[k] = str(lista[k].get("rotulo", lista[k].get("nome", "")))
		cores[k] = UtilPalco.cor(lista[k].get("cor_lado", 0xFFFFFF))
	tela = ctx.get("tela", tela)
	var tl = ctx.get("timeline")
	_planos = tl.tabela("planos") if tl != null else dados.get("planos", [])
	var negrito := FontVariation.new()
	negrito.base_font = ThemeDB.fallback_font
	negrito.variation_embolden = 0.9
	_fonte = negrito


func atualizar(amostra: Dictionary, ctx: Dictionary) -> void:
	quadro = int(ctx.get("quadro", 0))
	for k in 2:
		var s: Dictionary = amostra.get("p1" if k == 0 else "p2", {})
		hp[k] = clampf(float(s.get("hp", 1.0)), 0.0, 1.0)
		# o fantasma segura o dano ~0,3 s e escorre (por quadro de VIDEO: no
		# hitstop ele continua escorrendo, o que realca a pancada)
		if fantasma[k] < hp[k]:
			fantasma[k] = hp[k]
		else:
			fantasma[k] = maxf(hp[k], fantasma[k] - 0.012)
		var idx := int(s.get("plano", -1))
		plano[k] = str(_planos[idx]) if idx >= 0 and idx < _planos.size() else ""
		if hp[k] <= 0.0:
			plano[k] = "KO"
		plano_p[k] = clampf(float(s.get("plano_p", 0.0)), 0.0, 1.0)
	queue_redraw()


func _draw() -> void:
	var e := tela.y / REF.y
	var margem := 36.0 * e
	var larg := (tela.x - 3.0 * margem) / 2.0
	var y_nome := tela.y * 0.058
	var tam_nome := int(50 * e)
	var tam_plano := int(36 * e)
	var alt := 40.0 * e
	var borda := 4.0 * e
	for k in 2:
		var x := margem if k == 0 else tela.x - margem - larg
		var alinh := HORIZONTAL_ALIGNMENT_LEFT if k == 0 else HORIZONTAL_ALIGNMENT_RIGHT
		# nome (cortado com reticencias se nao couber em meia tela)
		var nome := _caber(nomes[k], larg, tam_nome)
		draw_string_outline(_fonte, Vector2(x, y_nome), nome, alinh, larg, tam_nome, int(10 * e), Color(0, 0, 0, 0.95))
		draw_string(_fonte, Vector2(x, y_nome), nome, alinh, larg, tam_nome, Color.WHITE)
		# vida
		var y_barra := y_nome + 16.0 * e
		var caixa := Rect2(x, y_barra, larg, alt)
		draw_rect(caixa.grow(borda), Color(0.02, 0.02, 0.04, 0.9), true)
		draw_rect(caixa, Color(0.12, 0.12, 0.16, 0.85), true)
		var cheio := larg * hp[k]
		var fant := larg * fantasma[k]
		var x_f := x if k == 0 else x + larg - fant
		draw_rect(Rect2(x_f, y_barra, fant, alt), Color(1.0, 0.93, 0.8, 0.9), true)
		var cor: Color = cores[k]
		if hp[k] < 0.25 and hp[k] > 0.0 and (quadro / 6) % 2 == 0:
			cor = cor.lerp(Color(1, 0.25, 0.2), 0.6)
		var x_c := x if k == 0 else x + larg - cheio
		draw_rect(Rect2(x_c, y_barra, cheio, alt), cor.darkened(0.25), true)
		draw_rect(Rect2(x_c, y_barra, cheio, alt * 0.55), cor, true)
		draw_rect(Rect2(x_c, y_barra + alt * 0.12, cheio, alt * 0.12), cor.lightened(0.35), true)
		draw_rect(caixa.grow(borda * 0.5), Color(1, 1, 1, 0.9), false, borda * 0.75)
		# plano
		if plano[k] != "":
			var y_plano := y_barra + alt + 16.0 * e + tam_plano
			var texto := _caber(plano[k], larg, tam_plano)
			var cor_p: Color = cores[k].lightened(0.45)
			draw_string_outline(_fonte, Vector2(x, y_plano), texto, alinh, larg, tam_plano, int(8 * e), Color(0, 0, 0, 0.95))
			draw_string(_fonte, Vector2(x, y_plano), texto, alinh, larg, tam_plano, cor_p)
			var largura_txt := _fonte.get_string_size(texto, HORIZONTAL_ALIGNMENT_LEFT, -1, tam_plano).x
			var x_t := x if k == 0 else x + larg - largura_txt
			var y_p := y_plano + 8.0 * e
			draw_rect(Rect2(x_t, y_p, largura_txt, 6.0 * e), Color(0, 0, 0, 0.7), true)
			draw_rect(Rect2(x_t, y_p, largura_txt * plano_p[k], 6.0 * e), cor_p, true)


func _caber(texto: String, largura: float, tamanho: int) -> String:
	if _fonte.get_string_size(texto, HORIZONTAL_ALIGNMENT_LEFT, -1, tamanho).x <= largura:
		return texto
	var t := texto
	while t.length() > 3 and _fonte.get_string_size(t + "…", HORIZONTAL_ALIGNMENT_LEFT, -1, tamanho).x > largura:
		t = t.substr(0, t.length() - 1)
	return t.strip_edges() + "…"
