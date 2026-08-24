"""Anexar as imagens de personagem e arma como REFERENCIA do video.

E a peca que resolve o problema que originou toda a mudanca: com prompt so de
texto, o mesmo personagem saiu de cabelo branco no clipe dele e de cabelo preto
no payoff (generation_00020), porque cada geracao reinterpretava as palavras do
zero. Anexando a imagem que ja foi gerada, o modelo tem o rosto na mao.

REGRA DURA: nada aqui levanta excecao. `anexar` devolve o que CONSEGUIU anexar
— possivelmente uma lista vazia — e quem chama decide o texto do prompt a
partir disso. O motivo e concreto: hoje esse video sai. Fazer o payoff falhar
por causa de um controle de upload que pode nao existir, ou que pode mudar no
proximo deploy, seria trocar um video imperfeito por nenhum video.

E tudo acontece ANTES de escrever o prompt e ANTES de clicar em enviar: falhar
aqui custa zero credito.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import artefato, slots

# Tetos de upload. Nao sao do site (nao ha como saber): sao do bom senso de
# nao mandar um PNG de 4000px para um formulario web. Acima disso a imagem e
# reencodada em JPEG antes de subir.
LADO_MAXIMO = 1536
MEGABYTES_MAXIMO = 8.0


def disponiveis(generation_id: str, ordem: list | None = None) -> list[Path]:
    """As imagens de referencia que existem no disco, na ordem pedida.

    Ordem importa quando o formulario aceita um arquivo so: a primeira da lista
    e a que vai. `character` vem antes de `weapon` porque rosto errado se nota
    muito mais que lamina errada.
    """
    # Se a imagem COMPOSTA existe, e ela a referencia — uma so, com as duas
    # identidades ja juntas pelo Editor Pro. O composer do Digen aceita um
    # arquivo, entao mandar as duas separadas nunca foi opcao.
    if artefato.utilizavel(generation_id, slots.REFERENCIA):
        return [artefato.caminho(generation_id, slots.REFERENCIA)]

    ordem = ordem or [slots.CHARACTER, slots.WEAPON]
    achados = []
    for slot in ordem:
        if slot not in slots.SLOTS or slots.midia(slot) != slots.IMAGEM:
            continue
        if artefato.utilizavel(generation_id, slot):
            achados.append(artefato.caminho(generation_id, slot))
    return achados


def slot_do_arquivo(caminho) -> str | None:
    """De volta do arquivo para o slot que o produziu.

    O prompt do payoff precisa saber QUAL lado ganhou imagem: com so uma
    referencia, o outro lado tem que continuar descrito por inteiro no texto.
    """
    nome = Path(caminho).name.lower()
    for slot in slots.SLOTS:
        for candidato in slots.nomes_aceitos(slot):
            base = Path(candidato).stem.lower()
            # PREFIXO, e nao igualdade: `para_upload` reduz a imagem e grava
            # `character_image_ref.jpg`. Comparar o nome inteiro devolvia None
            # para o arquivo que ACABOU de ser anexado, e o payoff caia na
            # variante de zero referencia com a imagem ja no formulario — o
            # anexo funcionava e o texto nao ficava sabendo.
            if nome == Path(candidato).name.lower() or nome.startswith(base):
                return slot
    return None


# Fracao do rodape que sai da imagem composta. O Editor Pro carimba texto ali
# (visto: "FEKRAN | OK T ... /DigMor") mesmo com "no text, no watermark, no
# logo" no prompt. Pedir e torcer nao serve quando a imagem vai virar video:
# o carimbo apareceria no payoff. Entao apara-se e pronto.
RODAPE = 0.06


def aparar_rodape(caminho: Path, fracao: float = RODAPE) -> Path:
    """Tira a faixa de baixo e reenquadra, mantendo a proporcao.

    Recorta tambem as laterais na medida certa para o resultado continuar
    9:16 — cortar so embaixo e esticar de volta deformaria o personagem.
    """
    try:
        from PIL import Image
        with Image.open(caminho) as original:
            imagem = original.convert("RGB")
            largura, altura = imagem.size
            nova_altura = int(altura * (1 - fracao))
            nova_largura = int(nova_altura * largura / altura)
            sobra = (largura - nova_largura) // 2
            recorte = imagem.crop((sobra, 0, sobra + nova_largura, nova_altura))
            recorte.resize((largura, altura), Image.LANCZOS).save(caminho)
        return caminho
    except Exception as exc:
        # Aparar e melhoria, nao requisito: com a imagem intacta o video ainda
        # sai, so com o carimbo.
        print(f"[anexo] nao consegui aparar o rodape ({exc}); segue inteira.")
        return caminho


def entradas_do_editor(generation_id: str) -> list[Path]:
    """As DUAS imagens que o Editor Pro recebe para compor.

    Separado de `disponiveis` de proposito: aquela responde "o que o Digen
    anexa" (a composta, quando ha), esta responde "o que entra no editor" (as
    duas cruas, sempre).
    """
    entradas = []
    for slot in (slots.CHARACTER, slots.WEAPON):
        if artefato.utilizavel(generation_id, slot):
            entradas.append(artefato.caminho(generation_id, slot))
    return entradas


def para_upload(caminho: Path, destino_dir: Path | None = None) -> Path:
    """O arquivo como ele vai subir: reencodado so se passar dos tetos.

    Devolve o proprio caminho quando ja esta dentro dos limites — o caso comum,
    e o que evita reescrever em disco a cada tentativa.
    """
    try:
        from PIL import Image
    except Exception:
        return caminho
    try:
        megas = caminho.stat().st_size / (1024 * 1024)
        with Image.open(caminho) as img:
            largura, altura = img.size
            if megas <= MEGABYTES_MAXIMO and max(largura, altura) <= LADO_MAXIMO:
                return caminho
            escala = min(1.0, LADO_MAXIMO / max(largura, altura))
            reduzida = img.convert("RGB").resize(
                (max(1, int(largura * escala)), max(1, int(altura * escala))),
                Image.LANCZOS)
        pasta = destino_dir or caminho.parent
        pasta.mkdir(parents=True, exist_ok=True)
        saida = pasta / f"{caminho.stem}_ref.jpg"
        reduzida.save(saida, quality=92)
        return saida
    except Exception:
        # Preparar a imagem nunca pode impedir o anexo: sobe a original.
        return caminho


# O composer aceita UMA imagem, e a segunda SUBSTITUI a primeira (verificado na
# tela em 24/08: entregar a arma depois do personagem deixava so a arma). Como
# o payoff precisa dos dois, a saida e mandar UMA imagem que contenha os dois.
LARGURA_INSET = 0.34
MARGEM_INSET = 0.035


def compor(personagem: Path, arma: Path, destino: Path) -> Path:
    """Uma folha de referencia: o personagem no quadro, a arma em destaque.

    O personagem ocupa o quadro inteiro porque e a identidade que mais se nota
    errada; a arma entra como painel no canto, com moldura, para ler como
    OBJETO SEPARADO e nao como parte da roupa.
    """
    from PIL import Image, ImageDraw

    with Image.open(personagem) as base:
        folha = base.convert("RGB").copy()
    largura, altura = folha.size

    with Image.open(arma) as bruta:
        arma_img = bruta.convert("RGB")
        alvo_l = max(1, int(largura * LARGURA_INSET))
        alvo_a = max(1, int(alvo_l * arma_img.height / arma_img.width))
        arma_img = arma_img.resize((alvo_l, alvo_a), Image.LANCZOS)

    margem = int(largura * MARGEM_INSET)
    x = largura - alvo_l - margem
    y = altura - alvo_a - margem
    desenho = ImageDraw.Draw(folha)
    borda = max(2, int(largura * 0.004))
    desenho.rectangle([x - borda, y - borda, x + alvo_l + borda, y + alvo_a + borda],
                      fill=(12, 12, 16))
    folha.paste(arma_img, (x, y))
    desenho.rectangle([x - borda, y - borda, x + alvo_l + borda, y + alvo_a + borda],
                      outline=(235, 233, 247), width=borda)

    destino.parent.mkdir(parents=True, exist_ok=True)
    folha.save(destino)
    return destino


def folha_de_referencia(generation_id: str, ordem: list | None = None) -> Path | None:
    """A imagem unica que o composer vai receber, ou None se nao houver as duas.

    Com so uma das imagens no disco, devolve None: quem chama usa a que existe
    sozinha, e o texto descreve o lado que falta.
    """
    achados = {slot_do_arquivo(c): c for c in disponiveis(generation_id, ordem)}
    personagem, arma = achados.get(slots.CHARACTER), achados.get(slots.WEAPON)
    if not (personagem and arma):
        return None
    from . import config
    destino = config.identity_dir(generation_id) / "referencia_folha.png"
    try:
        return compor(personagem, arma, destino)
    except Exception as exc:
        print(f"[anexo] nao consegui compor a folha ({exc}); "
              "vai so a imagem do personagem.")
        return None


def _entrada(page, sel):
    return sel.entrada_de_arquivo(page)


# O `blob:` da miniatura e criado pelo navegador no instante da escolha, entao
# a espera e curta de proposito: se em poucos segundos nada apareceu, o app
# recusou o arquivo e insistir so atrasa a fila.
ESPERA_MINIATURA = 8.0


def _miniaturas(page, sel) -> list:
    ver = getattr(sel, "miniaturas", None)
    if not callable(ver):
        return []
    try:
        return list(ver(page))
    except Exception:
        # Pagina morta no meio do anexo nao pode virar excecao: quem chama
        # trata "nao anexou" e segue com o prompt de texto.
        return []


def _esperar_miniatura(page, sel, quantas_antes: int,
                       timeout: float = ESPERA_MINIATURA) -> bool:
    """Esperou aparecer uma miniatura NOVA no composer?

    Esta e a unica prova aceitavel de que o anexo pegou. `set_input_files` nao
    levantar excecao nao prova nada: numa rodada real ele "funcionou" contra um
    input escondido que o app nem escuta, e o video saiu sem referencia
    nenhuma enquanto o log dizia que tinha anexado.
    """
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if len(_miniaturas(page, sel)) > quantas_antes:
            return True
        time.sleep(0.5)
    return False


def _fechar_menu(page) -> None:
    """Fecha o popover para ele nao ficar por cima do botao de enviar."""
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


def _abrir_menu_de_anexo(page, sel, rng=None) -> bool:
    """"+" -> "Upload Image". Devolve se chegou ao fim do caminho.

    O menu tem outros itens ("Select from Gallery", "Character Library") que
    NAO servem, entao a opcao e achada pelo rotulo, nunca por posicao.
    """
    botao = sel.encontrar(page, sel.BOTAO_ANEXO, timeout=2.0)
    if botao is None:
        return False
    try:
        botao.click()
    except Exception:
        return False
    if rng is not None:
        from .browser import pausa_humana
        pausa_humana(rng, 0.4, 1.0)
    opcao = sel.encontrar(page, sel.OPCAO_ENVIAR_IMAGEM, timeout=3.0)
    if opcao is None:
        _fechar_menu(page)
        return False
    try:
        opcao.click()
    except Exception:
        _fechar_menu(page)
        return False
    return True


def _pelo_dialogo(page, caminho: Path, sel, rng, timeout: float) -> bool:
    """"+" -> "Upload Image" -> dialogo nativo. E o caminho que FUNCIONA.

    Observado no site em 24/08/2026: clicar em "Upload Image" abre o seletor
    de arquivo do sistema, que o Playwright intercepta sem abrir janela do
    Windows. O input escondido do DOM existe, mas escrever nele direto nao
    registra nada no app.
    """
    try:
        with page.expect_file_chooser(timeout=timeout * 1000) as info:
            if not _abrir_menu_de_anexo(page, sel, rng):
                return False
        escolha = info.value
        escolha.set_files([str(caminho)])
        return True
    except Exception as exc:
        print(f"[anexo] dialogo de arquivo nao abriu ({type(exc).__name__}).")
        return False


def _pelo_input(page, caminho: Path, sel) -> bool:
    """Plano B: escrever no input escondido. Pode nao registrar no app."""
    entrada = _entrada(page, sel)
    if entrada is None:
        return False
    try:
        entrada.set_input_files([str(caminho)])
        return True
    except Exception:
        return False


def anexar(page, caminhos, sel, rng=None, timeout: float = 15.0,
           espera_miniatura: float = ESPERA_MINIATURA, maximo: int = 1) -> list:
    """Anexa o que der e devolve o que REALMENTE entrou. Nunca levanta.

    `maximo` e 1 por um motivo observado, nao por precaucao: o composer aceita
    uma imagem e a segunda SUBSTITUI a primeira. Insistir na segunda trocava o
    personagem pela arma e o contador de miniaturas nem percebia (substituir
    mantem a contagem em 1). Para levar as duas identidades, quem chama manda
    UMA folha composta — ver `folha_de_referencia`.

    Cada anexo so conta depois que a miniatura aparece no composer: e a
    checagem visual que separa "entreguei o arquivo" de "o app aceitou".
    """
    caminhos = [Path(c) for c in caminhos if c]
    if not caminhos:
        return []

    anexadas = []
    for caminho in caminhos[:max(1, int(maximo))]:
        antes = len(_miniaturas(page, sel))
        # Sem menu de anexo declarado nao ha dialogo para esperar: e o caso do
        # PicassoIA, cuja zona de "arraste e solte" e um input de verdade. Sem
        # esta guarda, cada imagem custava o timeout inteiro do `expect_file_
        # chooser` antes de cair no caminho que funciona.
        tem_menu = bool(getattr(sel, "BOTAO_ANEXO", None))
        entregue = ((tem_menu and _pelo_dialogo(page, caminho, sel, rng, timeout))
                    or _pelo_input(page, caminho, sel))
        if not entregue:
            print(f"[anexo] nao consegui entregar {caminho.name}.")
            break
        if not _esperar_miniatura(page, sel, antes, espera_miniatura):
            print(f"[anexo] {caminho.name} foi entregue mas o composer nao "
                  "mostrou miniatura: NAO conto como anexado.")
            break
        print(f"[anexo] {caminho.name} anexado (miniatura confirmada).")
        anexadas.append(caminho)
    return anexadas
