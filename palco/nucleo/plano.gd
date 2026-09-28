class_name PlanoQuadros
extends RefCounted
## O plano de quadros: para cada quadro do VIDEO, o instante da gravacao que
## ele mostra. E aqui que o corte de tedio e a camera lenta viram video sem
## nenhuma compressao intermediaria (o corte e renderizado direto).
##
## - Sem `remapeamento`: um trecho so, [0, duracao, 1].
## - Trecho [inicio, duracao, velocidade]: round(duracao / velocidade * fps)
##   quadros; o quadro j mostra o instante inicio + j * velocidade / fps.
## - Hitstop do render (estilo): quadros repetidos logo depois do quadro do
##   acerto. Tudo o que tem hora (eventos, sons) passa por `mapear()`, que ja
##   conta esses quadros.
##
## A MESMA conta existe em Python (builds/palco/plano.py) para conferir a
## duracao do mp4 sem abrir o Godot. Mudou aqui, mude la (ha teste).

var fps := 30
var trechos: Array = []            # [[inicio, duracao, velocidade], ...]
var t_src := PackedFloat64Array()  # instante da gravacao de cada quadro final
var trecho_de := PackedInt32Array()  # indice do trecho de cada quadro final
var parado := PackedByteArray()    # 1 = quadro de hitstop do render (repetido)
var _inicio_base := PackedInt32Array()  # primeiro quadro-base de cada trecho
var _n_base := PackedInt32Array()       # quadros-base de cada trecho
var _base_para_final := PackedInt32Array()


static func montar(duracao_total: float, remapeamento, taxa: int) -> PlanoQuadros:
	var p := PlanoQuadros.new()
	p.fps = taxa
	var lista: Array = []
	if typeof(remapeamento) == TYPE_DICTIONARY and typeof(remapeamento.get("trechos")) == TYPE_ARRAY and not remapeamento["trechos"].is_empty():
		for tr in remapeamento["trechos"]:
			var vel := float(tr[2]) if tr.size() > 2 else 1.0
			lista.append([float(tr[0]), float(tr[1]), vel])
	else:
		lista.append([0.0, duracao_total, 1.0])
	p.trechos = lista
	var base_t := PackedFloat64Array()
	var base_tr := PackedInt32Array()
	for k in lista.size():
		var ini: float = lista[k][0]
		var dur: float = lista[k][1]
		var vel: float = lista[k][2]
		var quantos := int(round(dur / vel * taxa))
		p._inicio_base.append(base_t.size())
		p._n_base.append(quantos)
		for j in quantos:
			base_t.append(ini + j * vel / taxa)
			base_tr.append(k)
	p._aplicar_paradas(base_t, base_tr, {})
	return p


## Acrescenta quadros parados: `paradas` = {quadro_base: quantos}.
func _aplicar_paradas(base_t: PackedFloat64Array, base_tr: PackedInt32Array, paradas: Dictionary) -> void:
	t_src = PackedFloat64Array()
	trecho_de = PackedInt32Array()
	parado = PackedByteArray()
	_base_para_final = PackedInt32Array()
	for b in base_t.size():
		_base_para_final.append(t_src.size())
		t_src.append(base_t[b])
		trecho_de.append(base_tr[b])
		parado.append(0)
		for _k in int(paradas.get(b, 0)):
			t_src.append(base_t[b])
			trecho_de.append(base_tr[b])
			parado.append(1)


## Refaz o plano com hitstop do render. `acertos` = [[t, segundos], ...].
func com_hitstop(acertos: Array) -> void:
	var base_t := PackedFloat64Array()
	var base_tr := PackedInt32Array()
	for k in trechos.size():
		for j in _n_base[k]:
			base_t.append(trechos[k][0] + j * trechos[k][2] / fps)
			base_tr.append(k)
	var paradas := {}
	for a in acertos:
		var b := _quadro_base(float(a[0]))
		var quantos := int(round(float(a[1]) * fps))
		if b >= 0 and quantos > 0:
			paradas[b] = max(int(paradas.get(b, 0)), quantos)
	_aplicar_paradas(base_t, base_tr, paradas)


func total() -> int:
	return t_src.size()


func duracao() -> float:
	return float(t_src.size()) / float(fps)


## Instante da gravacao -> quadro-base (antes das paradas); -1 se caiu num
## corte. Mesma tolerancia do `highlights.mapear_tempo` (1e-6 nas pontas).
func _quadro_base(t: float) -> int:
	for k in trechos.size():
		var ini: float = trechos[k][0]
		var dur: float = trechos[k][1]
		var vel: float = trechos[k][2]
		if t < ini - 1e-6:
			return -1
		if t <= ini + dur + 1e-6:
			var j := int(round((t - ini) / vel * fps))
			return _inicio_base[k] + clampi(j, 0, max(0, _n_base[k] - 1))
	return -1


## Instante da gravacao -> quadro do video final; -1 se caiu num corte.
func mapear(t: float) -> int:
	var b := _quadro_base(t)
	if b < 0 or b >= _base_para_final.size():
		return -1
	return _base_para_final[b]


## Quanto o mundo andou do quadro anterior a este, em fracao de quadro
## normal: 1 = velocidade normal, 0,5 = camera lenta, 0 = parado. O primeiro
## quadro de cada trecho (jump cut) vale 0: os efeitos recomecam do zero.
func velocidade(quadro: int) -> float:
	if quadro <= 0 or quadro >= t_src.size():
		return 1.0
	if trecho_de[quadro] != trecho_de[quadro - 1]:
		return 0.0
	return (t_src[quadro] - t_src[quadro - 1]) * fps


func inicio_de_trecho(quadro: int) -> bool:
	return quadro == 0 or (quadro < trecho_de.size() and trecho_de[quadro] != trecho_de[quadro - 1])
