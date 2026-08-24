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
    ordem = ordem or [slots.CHARACTER, slots.WEAPON]
    achados = []
    for slot in ordem:
        if slot not in slots.SLOTS or slots.midia(slot) != slots.IMAGEM:
            continue
        if artefato.utilizavel(generation_id, slot):
            achados.append(artefato.caminho(generation_id, slot))
    return achados


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


def _entrada(page, sel):
    return sel.entrada_de_arquivo(page)


def _abrir_menu_de_anexo(page, sel, rng=None) -> bool:
    """"+" -> "Enviar imagem". Devolve se chegou ao fim do caminho."""
    from .browser import pausa_humana
    botao = sel.encontrar(page, sel.BOTAO_ANEXO, timeout=2.0)
    if botao is None:
        return False
    try:
        botao.click()
    except Exception:
        return False
    if rng is not None:
        pausa_humana(rng, 0.4, 1.0)
    opcao = sel.encontrar(page, sel.OPCAO_ENVIAR_IMAGEM, timeout=3.0)
    if opcao is None:
        # O popover abriu e nao tem a opcao: fecha para nao deixar menu aberto
        # por cima do botao de enviar.
        with_escape(page)
        return False
    try:
        opcao.click()
    except Exception:
        with_escape(page)
        return False
    if rng is not None:
        pausa_humana(rng, 0.3, 0.8)
    return True


def with_escape(page) -> None:
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


def anexar(page, caminhos, sel, rng=None, timeout: float = 15.0) -> list[Path]:
    """Anexa o que der e devolve a lista do que de fato subiu. Nunca levanta.

    Tres degraus, do mais curto para o mais fragil:

      1. `input[type=file]` que JA esta no DOM. `set_input_files` funciona nele
         mesmo escondido (`display:none`), sem clicar em nada e sem depender de
         popover, timing ou idioma. E o caminho mais estavel que existe.
      2. "+" -> "Enviar imagem" e entao o input que apareceu.
      3. "+" -> "Enviar imagem" com captura do dialogo nativo de arquivo, para
         o caso de o site nao usar input nenhum.

    Se o formulario aceitar so um arquivo, a lista inteira falha e cada arquivo
    e tentado sozinho — melhor uma referencia que nenhuma.
    """
    caminhos = [Path(c) for c in caminhos if c]
    if not caminhos:
        return []

    entrada = _entrada(page, sel)
    if entrada is None and _abrir_menu_de_anexo(page, sel, rng):
        entrada = _entrada(page, sel)

    if entrada is not None:
        if _enviar(entrada, caminhos):
            return list(caminhos)
        # `multiple` ausente: o formulario aceita um arquivo por vez.
        for caminho in caminhos:
            if _enviar(entrada, [caminho]):
                return [caminho]
        return []

    return _pelo_dialogo(page, caminhos, sel, rng, timeout)


def _enviar(entrada, caminhos: list[Path]) -> bool:
    try:
        entrada.set_input_files([str(c) for c in caminhos])
        return True
    except Exception:
        return False


def _pelo_dialogo(page, caminhos, sel, rng, timeout: float) -> list[Path]:
    """Ultimo degrau: o site abre o dialogo nativo em vez de usar input."""
    try:
        with page.expect_file_chooser(timeout=timeout * 1000) as info:
            if not _abrir_menu_de_anexo(page, sel, rng):
                return []
        escolha = info.value
        escolha.set_files([str(c) for c in caminhos])
        return list(caminhos)
    except Exception:
        return []
