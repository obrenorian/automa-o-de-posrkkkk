# Meta Business Suite Reel Scheduler

Automatizador local para preparar e agendar Reels no Facebook e Instagram pela
interface web do Meta Business Suite. O projeto usa Python e Playwright, sem a
API da Meta, tokens de acesso ou armazenamento de senha.

> **Aviso:** automação de interface depende da estrutura atual do Meta Business
> Suite e pode exigir ajustes quando a Meta alterar a página. Use primeiro os
> comandos de teste e respeite os termos aplicáveis às suas contas.

## Estado atual

O fluxo de um Reel foi validado de ponta a ponta na interface em português:

1. reutiliza uma sessão persistente;
2. abre o compositor da página configurada;
3. confirma a conta do Instagram em **Postar em**;
4. envia e aguarda o processamento do vídeo;
5. preenche e relê a legenda;
6. aguarda a verificação de direitos autorais;
7. passa por **Editar** e **Compartilhar**;
8. programa data e hora para Facebook e Instagram;
9. clica uma vez no botão final;
10. só grava `SCHEDULED` quando a Meta mostra uma confirmação positiva.

O comando real processa **um ID por vez**. A fila automática, controles de
pausa/continuação e painel gráfico ainda fazem parte do roadmap.

## Requisitos

- Windows 10 ou 11;
- Python 3.12 ou mais recente;
- Google Chrome para o login manual;
- acesso ao Meta Business Suite com as páginas e contas do Instagram conectadas.

## Instalação

Abra o PowerShell na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Se a política do PowerShell bloquear a ativação, use o executável do ambiente
diretamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Configuração

### 1. Contas

Copie o modelo e edite o novo arquivo:

```powershell
Copy-Item accounts.example.json accounts.json
```

Cada chave é o nome interno usado no CSV:

```json
{
  "achadinhos01": {
    "instagram_name": "@achadinhos01",
    "business_id": "123456789012345",
    "page_id": "234567890123456",
    "asset_id": "234567890123456"
  }
}
```

Os identificadores aparecem na URL do compositor do Meta Business Suite. Por
exemplo, em uma URL com `business_id=123` e `page_id=456`, use esses valores sem
salvar `redirect_session_id`, pois ele é temporário. Em geral, `asset_id` tem o
mesmo valor de `page_id` nesse fluxo.

`accounts.json` é ignorado pelo Git para evitar publicar nomes e IDs reais.

### 2. Posts

Copie o modelo:

```powershell
Copy-Item posts.example.csv posts.csv
```

Formato esperado:

```csv
id,conta,video,legenda,data,hora
1,achadinhos01,C:\Videos\001.mp4,"Legenda do Reel",15/09/2026,08:10
```

Regras validadas antes da automação:

- as seis colunas são obrigatórias;
- `id` deve ser único;
- `conta` deve existir em `accounts.json`;
- o vídeo deve existir e usar `.mp4`, `.mov` ou `.m4v`;
- um mesmo arquivo de vídeo não pode aparecer duas vezes;
- data deve usar `DD/MM/AAAA` e hora, `HH:MM` em formato de 24 horas;
- o horário precisa estar no futuro conforme o relógio local do Windows.

O arquivo real `posts.csv` e arquivos de vídeo também são ignorados pelo Git.

## Primeiro login

O login é feito manualmente em um Chrome normal para permitir CAPTCHA, 2FA e
confirmação de dispositivo sem qualquer tentativa de automação:

```powershell
python main.py --manual-login --profile-dir ".\browser_profile"
```

Faça login no Facebook, abra o Meta Business Suite e confirme que ele funciona.
Depois feche todas as janelas abertas com esse perfil. Cookies e sessão ficam
somente em `browser_profile`, que nunca deve ser enviado ao Git.

Não abra dois navegadores simultaneamente com o mesmo `--profile-dir`.

## Uso seguro, passo a passo

### 1. Validar os arquivos

```powershell
python main.py --validate-only
```

### 2. Conferir a fila sem operar a Meta

```powershell
python main.py --dry-run --limit 3
```

O dry-run valida, importa os dados no SQLite e lista os itens pendentes. Ele não
abre o compositor nem publica conteúdo.

### 3. Testar a sessão

```powershell
python main.py --test-session
```

### 4. Testar cada etapa sem publicar

```powershell
python main.py --test-create-reel
python main.py --test-account achadinhos01
python main.py --test-upload 1
python main.py --test-caption 1
python main.py --test-next 1
python main.py --test-schedule-screen 1
python main.py --test-schedule-form 1
python main.py --test-schedule-values 1
```

Os comandos param progressivamente no ponto indicado. Em especial,
`--test-schedule-values` preenche e relê os horários, mas não clica no botão
final **Programar**.

### 5. Agendar um Reel real

```powershell
python main.py --schedule-post 1 --manual-confirm
```

O modo assistido mostra conta, arquivo, data e hora e pede `[S/N]` imediatamente
antes do clique final. Depois de ganhar confiança no ambiente, a confirmação
manual pode ser omitida:

```powershell
python main.py --schedule-post 1
```

O sucesso exige uma mensagem inequívoca da Meta, como **Reel programado**. Um
clique sem confirmação deixa o item `SKIPPED` para impedir reenvio acidental;
confira o Planner manualmente antes de alterar seu estado.

## Opções principais

| Opção | Efeito |
| --- | --- |
| `--csv CAMINHO` | Usa outro arquivo de posts |
| `--accounts CAMINHO` | Usa outro arquivo de contas |
| `--database CAMINHO` | Usa outro banco SQLite |
| `--profile-dir CAMINHO` | Define o perfil persistente do navegador |
| `--browser-channel chrome` | Executa a automação com o Chrome instalado |
| `--limit N` | Limita itens exibidos pelo dry-run |
| `--reprocess-failures` | Devolve itens `FAILED` para `PENDING` |
| `--manual-confirm` | Exige confirmação antes do envio real |

Use os mesmos caminhos em todas as etapas quando fornecer opções customizadas.

## Estados e proteção contra duplicidade

O arquivo `scheduler.db` armazena `id`, conta, vídeo, data, hora, status,
tentativas, erro e timestamp do agendamento.

| Estado | Significado |
| --- | --- |
| `PENDING` | Pronto para processamento |
| `PROCESSING` | Fluxo em andamento |
| `SCHEDULED` | Confirmação positiva recebida da Meta |
| `FAILED` | Falha anterior ao envio ou falha recuperável |
| `SKIPPED` | Bloqueado para revisão, inclusive após envio com retorno incerto |

IDs em `SCHEDULED` nunca são reabertos pela importação. O clique final é
executado uma vez e a aplicação evita repetir um ID com estado protegido.

Para devolver somente falhas à fila:

```powershell
python main.py --dry-run --reprocess-failures
```

## Logs e diagnósticos

- `logs/app.log`: eventos estruturados do fluxo;
- `logs/*.html`: HTML salvo em testes ou falhas;
- `screenshots/*.png`: evidências visuais;
- `scheduler.db`: estado local da fila;
- `browser_profile/`: cookies e sessão.

Esses arquivos são locais e ignorados pelo Git. Revise qualquer diagnóstico
antes de compartilhá-lo, pois a tela pode conter nomes de contas e conteúdo.

## Testes automatizados

```powershell
python -m unittest discover -s tests -v
```

Os testes cobrem validação de entrada, persistência, roteamento da CLI e os
principais seletores/estados do fluxo Playwright. Eles usam páginas HTML locais
e não publicam nada na Meta.

## Estrutura

```text
app/
  automation/     navegador, URLs, seletores e fluxo do Meta Business Suite
  database/       persistência SQLite e transições de estado
  models/         modelos de post e status
  services/       leitura e validação do CSV/JSON
  ui/             reservado para o painel local
tests/             testes unitários e de componentes Playwright
docs/              arquitetura e solução de problemas
main.py            ponto de entrada
```

Leia também [Arquitetura](docs/ARCHITECTURE.md),
[Solução de problemas](docs/TROUBLESHOOTING.md) e
[Segurança](SECURITY.md).

## Limitações e roadmap

- seletores foram validados na interface em português e podem precisar de
  manutenção quando a Meta mudar o compositor;
- o executor real atual agenda um ID por comando;
- processamento automático de toda a fila e rate control são os próximos passos;
- pausa, continuação, parada e dashboard ainda não estão implementados;
- CAPTCHA, 2FA e confirmações de segurança sempre exigem intervenção humana.
