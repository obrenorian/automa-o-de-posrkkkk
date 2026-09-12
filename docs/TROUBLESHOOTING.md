# Solução de problemas

## O login abre em branco ou o Google não carrega

Faça a autenticação no Chrome normal, fora do Playwright:

```powershell
python main.py --manual-login --profile-dir ".\browser_profile"
```

Conclua login, CAPTCHA ou 2FA, visite o Meta Business Suite e feche todas as
janelas desse perfil antes de iniciar a automação.

## `Abrindo em uma sessão de navegador existente`

Outro Chrome/Chromium está usando o mesmo perfil. Feche essa janela e confirme no
Gerenciador de Tarefas que a instância terminou. Não apague o perfil: ele contém
a sessão autenticada.

## A janela maximiza, mas o site mantém uma área pequena

Use a versão atual de `browser.py`, que inicia o contexto com viewport nativo.
Evite reaproveitar um processo antigo do navegador depois de atualizar o código.

## Campo de legenda não encontrado

A Meta provavelmente alterou o nome acessível do editor. Rode:

```powershell
python main.py --test-caption ID
```

Consulte o HTML e a captura salvos em `logs/` e `screenshots/`. Atualize somente
os fallbacks centralizados em `app/automation/selectors.py`.

## Timeout nos campos de data ou hora

Esses campos são componentes React e podem recriar o elemento durante a edição.
O fluxo atual digita pelo teclado da página e relocaliza cada controle. Confirme
que o relógio e o fuso horário do Windows estão corretos e que a data está no
futuro.

## O item ficou `SKIPPED`

Isso pode significar que o clique foi enviado, mas a confirmação não pôde ser
lida. Abra o Planner do Meta Business Suite e pesquise o Reel antes de qualquer
nova tentativa. Essa trava existe para evitar uma publicação duplicada.

## Onde encontrar evidências

- log principal: `logs/app.log`;
- screenshots: `screenshots/`;
- HTML da tela: `logs/*.html`;
- estado: `scheduler.db`.

Esses arquivos podem conter dados das contas. Remova informações pessoais antes
de anexá-los a uma issue pública.
