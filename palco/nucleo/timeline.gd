class_name Timeline
extends RefCounted
## A timeline v1 (docs/palco/timeline.md): o contrato simulacao -> palco.
##
## O palco SO LE este arquivo; nada aqui decide a luta. Um passo do motor a
## 60 Hz por amostra: o quadro k do video de 30 fps e o passo 2k. O relogio
## de `eventos` e o numero do passo (t = i / hz); o de `sons` e o do video do
## gravador (quantizado ao quadro); o de `remapeamento` e o da gravacao bruta.
## Nos tres casos, sem corte de tedio, "segundo s" = passo s * hz.

const FORMATO := "neural-fights/timeline"
const VERSAO := 1
# Revisao ADITIVA mais nova que o palco conhece (docs/palco/timeline.md). Uma
# timeline de revisao MAIOR continua valida: o leitor ignora o que nao conhece.
const REVISAO := 3
# Eventos que viram efeito na tela (os outros vao so para as pecas, em
# evento()). Revisao 3: explosao (a paleta do elemento) e choque (duas cores),
# com as texturas CC0 que a biblioteca ja tem.
const EVENTOS_COM_VFX := {
	"acerto": true, "dano": true, "cura": true, "bloqueio": true, "parry": true,
	"esquiva": true, "desvio": true, "dash": true, "parede": true, "wall_splat": true,
	"ko": true, "escudo_quebrou": true, "skill": true, "agarrao_desfecho": true,
	"obstaculo": true, "explosao": true, "choque": true,
}
# Campos obrigatorios dos eventos da revisao 3 (o mesmo que
# timeline.CAMPOS_EVENTOS_R3 no Python). Timeline antiga nao tem nenhum.
const CAMPOS_EVENTO := {
	"projetil_fim": ["id", "objeto", "motivo", "x", "y"],
	"explosao": ["x", "y", "origem"],
	"choque": ["x", "y", "origem"],
	"refletido": ["id", "de", "para", "x", "y"],
	"texto": ["texto_id", "texto", "estilo", "x", "y"],
	"movimento": ["gatilho", "vfx", "x", "y"],
}
const MOTIVOS_FIM := ["choque", "explodiu", "expirou", "voltou", "trap", "acerto", "bloqueado", "sumiu"]

const CANAIS_LUTADOR := [
	"x", "y", "z", "ang", "vx", "vy", "hp", "mp", "est", "expr", "acao", "plano",
	"plano_p", "tell", "flags", "golpe_fase", "golpe_p", "golpe_d", "golpe_id",
	"golpe_janela", "anim_fase", "anim_p", "arma_ang", "arma_lunge", "arma_gx",
	"arma_gy", "arma_px", "arma_py", "arma_puxada", "hb_on", "hb_ang", "hb_larg",
	"escudo", "combo", "flash", "flash_cor", "esc_x", "esc_y",
]
const CANAIS_CAMERA := ["x", "y", "zoom", "lv", "av", "ox", "oy"]
const CANAIS_GLOBAIS := ["tj", "escala", "hitstop", "letterbox", "fim"]
const CANAIS_OBJETO := {
	"projetil": ["x", "y", "r", "ang", "prog"],
	"projetil_arma": ["x", "y", "r", "ang", "prog"],
	"orbe": ["x", "y", "r", "estado"],
	"area": ["x", "y", "r", "ativ", "prog"],
	"beam": ["larg", "prog"],
	"summon": ["x", "y", "ang", "hp", "prog"],
	"trap": ["x", "y", "hp", "prog"],
	"portal": ["prog"],
}
const CANAIS_EFEITO := {
	"status": ["rest"],
	"buff": ["rest", "escudo"],
	"canal": ["prog", "ang"],
	"transformacao": ["prog"],
}
# Canais que podem ser interpolados entre dois passos (camera lenta do palco).
# Os outros sao discretos (indice, bits, contador) e pegam o passo de baixo.
const _CONTINUOS := {
	"x": true, "y": true, "z": true, "vx": true, "vy": true, "hp": true, "mp": true,
	"est": true, "plano_p": true, "arma_lunge": true, "arma_gx": true, "arma_gy": true,
	"arma_px": true, "arma_py": true, "arma_puxada": true, "escudo": true, "flash": true,
	"esc_x": true, "esc_y": true, "zoom": true, "lv": true, "av": true, "ox": true,
	"oy": true, "tj": true, "r": true, "larg": true, "prog": true, "rest": true,
}
const _ANGULOS := {"ang": true, "arma_ang": true, "hb_ang": true}

var dados: Dictionary = {}
var caminho := ""
var hz := 60
var n := 0
var erro := ""


## Le JSON puro ou o container comprimido do Godot (cabecalho "GCPF", o que
## FileAccess.open_compressed escreve). Devolve null e deixa o motivo em
## Timeline.ultimo_erro quando nao consegue.
static var ultimo_erro := ""


static func carregar(arquivo: String) -> Timeline:
	ultimo_erro = ""
	var texto := _ler_texto(arquivo)
	if texto.is_empty():
		ultimo_erro = "nao li %s (erro %d)" % [arquivo, FileAccess.get_open_error()]
		return null
	var json := JSON.new()
	if json.parse(texto) != OK:
		ultimo_erro = "JSON invalido em %s, linha %d: %s" % [arquivo, json.get_error_line(), json.get_error_message()]
		return null
	return de_dicionario(json.data, arquivo)


static func de_dicionario(d, origem: String = "") -> Timeline:
	if typeof(d) != TYPE_DICTIONARY:
		ultimo_erro = "a timeline nao e um objeto JSON (%s)" % origem
		return null
	var tl := Timeline.new()
	tl.dados = d
	tl.caminho = origem
	tl.hz = int(d.get("hz", 60))
	tl.n = int(d.get("n", 0))
	return tl


static func _ler_texto(arquivo: String) -> String:
	var f := FileAccess.open(arquivo, FileAccess.READ)
	if f == null:
		return ""
	var magia := f.get_buffer(4)
	f.close()
	if magia.get_string_from_ascii() == "GCPF":
		# O modo de compressao esta no cabecalho; o parametro so vale para escrever.
		var c := FileAccess.open_compressed(arquivo, FileAccess.READ, FileAccess.COMPRESSION_ZSTD)
		if c == null:
			return ""
		return c.get_as_text()
	return FileAccess.get_file_as_string(arquivo)


# ------------------------------------------------------------------ validacao
## Lista de problemas (vazia = valida). O palco recusa renderizar timeline
## invalida (rc 2); `ferramentas/validar.gd` imprime esta lista.
func validar() -> PackedStringArray:
	var e := PackedStringArray()
	if dados.get("formato") != FORMATO:
		e.append("formato %s != %s" % [str(dados.get("formato")), FORMATO])
	if not _eh_numero(dados.get("versao")) or int(dados.get("versao")) != VERSAO:
		e.append("versao %s != %d" % [str(dados.get("versao")), VERSAO])
	if dados.has("revisao") and (not _eh_numero(dados.get("revisao")) or int(dados.get("revisao")) < 1):
		e.append("revisao invalida: %s" % str(dados.get("revisao")))
	if not _eh_numero(dados.get("hz")) or hz <= 0:
		e.append("hz invalido: %s" % str(dados.get("hz")))
	if not _eh_numero(dados.get("n")) or n <= 0:
		e.append("n invalido: %s" % str(dados.get("n")))
		return e
	var trilhas = dados.get("trilhas")
	if typeof(trilhas) != TYPE_DICTIONARY:
		e.append("sem trilhas")
		return e
	_conferir_canais(e, "trilhas.global", trilhas.get("global"), CANAIS_GLOBAIS, n)
	_conferir_canais(e, "trilhas.camera", trilhas.get("camera"), CANAIS_CAMERA, n)
	var lut = trilhas.get("lutadores")
	if typeof(lut) != TYPE_DICTIONARY:
		e.append("sem trilhas.lutadores")
	else:
		for slot in ["p1", "p2"]:
			_conferir_canais(e, "trilhas.lutadores.%s" % slot, lut.get(slot), CANAIS_LUTADOR, n)
	var cab = dados.get("lutadores")
	if typeof(cab) != TYPE_ARRAY or cab.size() != 2:
		e.append("cabecalho `lutadores` precisa de 2 entradas")
	else:
		for i in 2:
			var l = cab[i]
			if typeof(l) != TYPE_DICTIONARY:
				e.append("lutadores[%d] nao e objeto" % i)
			elif not _eh_numero(l.get("raio_corpo")) or float(l.get("raio_corpo")) <= 0.0:
				e.append("lutadores[%d].raio_corpo invalido" % i)
	_conferir_intervalos(e, "objetos", trilhas.get("objetos", []), CANAIS_OBJETO)
	_conferir_intervalos(e, "efeitos", trilhas.get("efeitos", []), CANAIS_EFEITO)
	_conferir_eventos(e)
	_conferir_sons(e)
	_conferir_remapeamento(e)
	return e


static func _eh_numero(v) -> bool:
	return typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT


func _conferir_canais(e: PackedStringArray, onde: String, bloco, canais: Array, tamanho: int) -> void:
	if typeof(bloco) != TYPE_DICTIONARY:
		e.append("%s ausente" % onde)
		return
	for c in canais:
		var arr = bloco.get(c)
		if typeof(arr) != TYPE_ARRAY:
			e.append("%s.%s ausente" % [onde, c])
		elif arr.size() != tamanho:
			e.append("%s.%s tem %d amostras, esperado %d" % [onde, c, arr.size(), tamanho])


func _conferir_intervalos(e: PackedStringArray, onde: String, lista, canais_por_tipo: Dictionary) -> void:
	if typeof(lista) != TYPE_ARRAY:
		e.append("trilhas.%s nao e lista" % onde)
		return
	for k in lista.size():
		var t = lista[k]
		if typeof(t) != TYPE_DICTIONARY:
			e.append("%s[%d] nao e objeto" % [onde, k])
			continue
		var i0 = t.get("i0")
		var i1 = t.get("i1")
		if not _eh_numero(i0) or not _eh_numero(i1) or int(i0) < 0 or int(i1) < int(i0) or int(i1) >= n:
			e.append("%s[%d] (%s): intervalo [%s, %s] fora de [0, %d)" % [onde, k, str(t.get("tipo")), str(i0), str(i1), n])
			continue
		var canais: Array = canais_por_tipo.get(str(t.get("tipo")), [])
		var tamanho := int(i1) - int(i0) + 1
		for c in canais:
			var arr = t.get(c)
			if typeof(arr) != TYPE_ARRAY or arr.size() != tamanho:
				e.append("%s[%d] (%s).%s: esperado %d amostras" % [onde, k, str(t.get("tipo")), c, tamanho])


func _conferir_eventos(e: PackedStringArray) -> void:
	var eventos = dados.get("eventos", [])
	if typeof(eventos) != TYPE_ARRAY:
		e.append("eventos nao e lista")
		return
	var anterior := -1
	for k in eventos.size():
		var ev = eventos[k]
		if typeof(ev) != TYPE_DICTIONARY or not _eh_numero(ev.get("i")) or typeof(ev.get("tipo")) != TYPE_STRING:
			e.append("evento %d sem i/tipo" % k)
			continue
		var i := int(ev.get("i"))
		if i < 0 or i >= n:
			e.append("evento %d (%s): i=%d fora de [0, %d)" % [k, ev.get("tipo"), i, n])
		if i < anterior:
			e.append("evento %d (%s): i=%d volta no tempo (anterior %d)" % [k, ev.get("tipo"), i, anterior])
		anterior = i
		_conferir_campos(e, k, ev)


## Os campos dos eventos da revisao 3 e o `ponto` do acerto por projetil.
## Tipo desconhecido passa (o leitor ignora o que nao conhece).
func _conferir_campos(e: PackedStringArray, k: int, ev: Dictionary) -> void:
	var tipo := str(ev.get("tipo"))
	if tipo == "acerto" and ev.has("ponto"):
		var p = ev.get("ponto")
		if typeof(p) != TYPE_ARRAY or p.size() != 2 or not _eh_numero(p[0]) or not _eh_numero(p[1]):
			e.append("evento %d (acerto): ponto %s nao e [x, y]" % [k, str(p)])
	if not CAMPOS_EVENTO.has(tipo):
		return
	for campo in CAMPOS_EVENTO[tipo]:
		if ev.get(campo) == null:
			e.append("evento %d (%s) sem %s" % [k, tipo, campo])
			return
	if not _eh_numero(ev.get("x")) or not _eh_numero(ev.get("y")):
		e.append("evento %d (%s): x/y nao sao numeros" % [k, tipo])
	if tipo == "projetil_fim" and not MOTIVOS_FIM.has(str(ev.get("motivo"))):
		e.append("evento %d (projetil_fim): motivo %s desconhecido" % [k, str(ev.get("motivo"))])
	if tipo == "movimento" and typeof(ev.get("vfx")) != TYPE_ARRAY:
		e.append("evento %d (movimento): vfx nao e lista" % k)


func _conferir_sons(e: PackedStringArray) -> void:
	var sons = dados.get("sons")
	if sons == null:
		return
	if typeof(sons) != TYPE_DICTIONARY or typeof(sons.get("itens")) != TYPE_ARRAY:
		e.append("sons precisa ser null ou {versao, relogio, itens: [...]}")
		return
	var limite := duracao() + 1.0
	var anterior := -1.0
	var itens: Array = sons["itens"]
	for k in itens.size():
		var s = itens[k]
		if typeof(s) != TYPE_DICTIONARY:
			e.append("som %d nao e objeto" % k)
			continue
		if not _eh_numero(s.get("t")) or float(s.get("t")) < 0.0 or float(s.get("t")) > limite:
			e.append("som %d: t=%s fora de [0, %.2f]" % [k, str(s.get("t")), limite])
			continue
		if typeof(s.get("id")) != TYPE_STRING or str(s.get("id")).is_empty():
			e.append("som %d sem id" % k)
		if _eh_numero(s.get("pitch")) and float(s.get("pitch")) <= 0.0:
			e.append("som %d: pitch %s <= 0" % [k, str(s.get("pitch"))])
		if float(s.get("t")) < anterior - 1e-6:
			e.append("som %d: t=%.3f volta no tempo" % [k, float(s.get("t"))])
		anterior = float(s.get("t"))


func _conferir_remapeamento(e: PackedStringArray) -> void:
	var r = dados.get("remapeamento")
	if r == null:
		return
	if typeof(r) != TYPE_DICTIONARY or typeof(r.get("trechos")) != TYPE_ARRAY:
		e.append("remapeamento precisa ser null ou {relogio, trechos: [[inicio, duracao, velocidade]]}")
		return
	var fim_anterior := -1.0
	var total := duracao() + 0.05
	for k in r["trechos"].size():
		var tr = r["trechos"][k]
		if typeof(tr) != TYPE_ARRAY or tr.size() < 2:
			e.append("trecho %d invalido" % k)
			continue
		var ini := float(tr[0])
		var dur := float(tr[1])
		var vel := float(tr[2]) if tr.size() > 2 else 1.0
		if ini < 0.0 or dur <= 0.0 or vel <= 0.0:
			e.append("trecho %d: [%s] com inicio<0, duracao<=0 ou velocidade<=0" % [k, str(tr)])
		if ini + dur > total:
			e.append("trecho %d passa do fim da timeline (%.2f > %.2f)" % [k, ini + dur, total])
		if ini < fim_anterior - 1e-3:
			e.append("trecho %d sobrepoe o anterior" % k)
		fim_anterior = ini + dur


# ------------------------------------------------------------------ leitura
func duracao() -> float:
	return float(n) / float(hz)


## Revisao da timeline (1 quando o arquivo nao traz o campo).
func revisao() -> int:
	return int(dados.get("revisao", 1)) if _eh_numero(dados.get("revisao", 1)) else 1


func cabecalho_lutador(slot: String) -> Dictionary:
	for l in dados.get("lutadores", []):
		if typeof(l) == TYPE_DICTIONARY and l.get("slot") == slot:
			return l
	return {}


func tabela(nome: String) -> Array:
	return dados.get("tabelas", {}).get(nome, [])


func trilhas() -> Dictionary:
	return dados.get("trilhas", {})


## Passo (fracionario) do relogio de segundos `t`.
func passo_de(t: float) -> float:
	return clampf(t * hz, 0.0, float(n - 1))


## Amostra de um bloco de canais {nome: [valores]} no passo fracionario `p`.
## Canal continuo e interpolado; angulo pelo caminho curto; o resto pega o
## passo de baixo. `desloc` e o primeiro passo do bloco (trilhas de objeto).
static func amostra(bloco: Dictionary, canais: Array, p: float, desloc: int = 0) -> Dictionary:
	var saida := {}
	var i0 := int(floorf(p)) - desloc
	var w := p - floorf(p)
	for nome in canais:
		var arr = bloco.get(nome)
		if typeof(arr) != TYPE_ARRAY or arr.is_empty():
			continue
		var tam: int = arr.size()
		var a := clampi(i0, 0, tam - 1)
		var b := clampi(a + 1, 0, tam - 1)
		if w < 1e-4 or a == b:
			saida[nome] = arr[a]
		elif _ANGULOS.has(nome):
			saida[nome] = rad_to_deg(lerp_angle(deg_to_rad(float(arr[a])), deg_to_rad(float(arr[b])), w))
		elif _CONTINUOS.has(nome):
			saida[nome] = lerpf(float(arr[a]), float(arr[b]), w)
		else:
			saida[nome] = arr[a]
	return saida


func lutador(slot: String, p: float) -> Dictionary:
	var bloco: Dictionary = trilhas().get("lutadores", {}).get(slot, {})
	var s := amostra(bloco, CANAIS_LUTADOR, p)
	# O progresso do golpe so interpola dentro da MESMA fase.
	var i := clampi(int(floor(p)), 0, n - 1)
	var j := clampi(i + 1, 0, n - 1)
	for par in [["golpe_fase", "golpe_p"], ["anim_fase", "anim_p"]]:
		var fases: Array = bloco.get(par[0], [])
		var progs: Array = bloco.get(par[1], [])
		if fases.size() == n and progs.size() == n and fases[i] != fases[j]:
			s[par[1]] = progs[i]
	return s


func camera(p: float) -> Dictionary:
	return amostra(trilhas().get("camera", {}), CANAIS_CAMERA, p)


func global(p: float) -> Dictionary:
	return amostra(trilhas().get("global", {}), CANAIS_GLOBAIS, p)


## Trilhas (objetos ou efeitos) vivas no passo `i`.
func vivas(colecao: String, i: int) -> Array:
	var saida := []
	for t in trilhas().get(colecao, []):
		if int(t["i0"]) <= i and i <= int(t["i1"]):
			saida.append(t)
	return saida


func amostra_trilha(t: Dictionary, p: float) -> Dictionary:
	var canais: Array = CANAIS_OBJETO.get(t.get("tipo"), CANAIS_EFEITO.get(t.get("tipo"), []))
	return amostra(t, canais, p, int(t["i0"]))
