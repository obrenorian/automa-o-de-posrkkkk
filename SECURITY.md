# Segurança

## Dados que nunca devem ser publicados

- diretórios `browser_profile*`;
- `accounts.json` e `posts.csv` reais;
- `scheduler.db` e seus arquivos auxiliares;
- logs, screenshots e HTML de diagnóstico;
- vídeos e outros arquivos de mídia.

O `.gitignore` cobre esses caminhos, mas confira `git status` antes de cada
commit. O perfil do navegador pode conter cookies capazes de acessar sua conta.

## Autenticação

O projeto não solicita nem armazena senha. Login, CAPTCHA, 2FA e confirmação de
dispositivo devem ser resolvidos manualmente. Não adicione técnicas de evasão ou
tentativas de contornar mecanismos de segurança.

## Relato de vulnerabilidades

Não abra uma issue pública contendo cookies, IDs privados, URLs de sessão ou
capturas da conta. Ao compartilhar um diagnóstico, produza antes uma cópia
anonimizada.
