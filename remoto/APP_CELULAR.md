# App do celular

Uma página instalável (PWA) que mostra o que as fábricas estão fazendo:
próxima postagem, pausa, fábricas, erros, diário ao vivo, vídeos prontos para
assistir e os relatórios do bot. **Nesta fase o app só lê.** Ele não publica,
não gera e não pausa nada.

O código está em `api_http.py` (servidor), `painel_dados.py` (o que é lido) e
`app/` (a página).

## Rede: `tailscale serve` sim, `tailscale funnel` NUNCA

A máquina tem YouTube, TikTok, ChatGPT e PicassoIA logados. O app só é visível
dentro da rede privada do Tailscale:

```bash
python -m remoto.api_http --local            # 127.0.0.1:8931
tailscale serve --bg --https=443 http://127.0.0.1:8931
tailscale serve status                       # tem que dizer "(tailnet only)"
```

O celular abre `https://<máquina>.<tailnet>.ts.net/` com o app do Tailscale
ligado.

- **`tailscale funnel` publica na internet.** Não use, em hipótese nenhuma.
- **Porta 8765:** é do login OAuth do YouTube, e o servidor recusa essa porta.
- **Sem o `serve`:** o servidor também sobe direto no IP 100.x (sem
  `--local`), mas sem HTTPS a página não fica instalável.

## Parear e esquecer

```bash
python -m remoto.api_http --parear        # código de 6 dígitos, 5 min, uma vez
python -m remoto.api_http --aparelhos     # id  nome  desde
python -m remoto.api_http --esquecer <id> # o id de 8 letras da lista
```

- **Onde fica a senha:** no disco (`%LOCALAPPDATA%/neural-fights/app_celular.json`)
  fica só o hash de cada token. O token em si existe só no celular.
- **Esquecer um aparelho:** derruba na hora o acesso dele e os links de vídeo
  que ele tinha.

## Desligar

```bash
tailscale serve --https=443 off
```

Depois, pare o processo `python -m remoto.api_http`. Não deixe o `serve`
ligado apontando para um servidor parado.
