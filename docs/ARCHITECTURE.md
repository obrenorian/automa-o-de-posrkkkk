# Arquitetura

## Visão geral

O projeto separa dados, automação de interface e persistência. Essa divisão
permite ajustar seletores do Meta Business Suite sem misturar regras de CSV ou
controle de status.

```text
posts.csv + accounts.json
          |
          v
 validação de entrada
          |
          v
      SQLite local
          |
          v
 fluxo Playwright ---> Meta Business Suite
          |
          v
 confirmação visível ---> SCHEDULED
```

## Componentes

- `app/main.py`: argumentos de linha de comando e orquestração das fases.
- `app/config.py`: caminhos e configurações locais.
- `app/services/input_loader.py`: leitura e validação de contas e posts.
- `app/database/database.py`: esquema SQLite, importação idempotente e estados.
- `app/automation/browser.py`: contexto Playwright visível e persistente.
- `app/automation/manual_browser.py`: Chrome comum para login, CAPTCHA e 2FA.
- `app/automation/account_urls.py`: URL estável por página, sem session ID.
- `app/automation/selectors.py`: seletores semânticos e fallbacks centralizados.
- `app/automation/meta_business.py`: operações do compositor e verificações.

## Fluxo de um agendamento

1. O CSV e o JSON são validados por completo.
2. O post é importado de forma idempotente no SQLite.
3. A transição para `PROCESSING` incrementa `tentativas`.
4. A conta exibida é confirmada antes do upload.
5. Cada etapa do compositor exige um marcador visível da tela seguinte.
6. Data e hora são relidas em todos os destinos selecionados.
7. O botão final é clicado uma vez.
8. Apenas uma confirmação positiva da Meta permite `SCHEDULED`.
9. Um resultado incerto após o clique vira `SKIPPED`, evitando duplicidade.

## Estratégia de seletores

Seletores ficam em `selectors.py` e priorizam:

1. papel acessível e nome (`get_by_role`);
2. rótulo, placeholder ou texto visível;
3. atributos semânticos estáveis;
4. mais de uma alternativa quando a interface tem variações conhecidas.

Posições CSS profundas e classes geradas pela Meta são evitadas. Os poucos
usos de ordem DOM distinguem botões com o mesmo nome acessível e possuem testes.

## Persistência e privacidade

O perfil do navegador, o banco, os arquivos reais de entrada e os diagnósticos
nunca fazem parte do repositório. O perfil persistente contém a sessão; não é
necessário nem permitido guardar senha no código.

## Extensão para lote

O próximo executor deve consumir `Database.pending(limit)`, isolar exceções por
item, respeitar pausa/parada entre Reels e manter `SKIPPED` fora de retentativas
automáticas. A camada de UI deve comandar esse executor sem duplicar a lógica de
automação.
