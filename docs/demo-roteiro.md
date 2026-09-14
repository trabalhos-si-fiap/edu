# Roteiro automatizado da demonstração

`scripts/demo_roteiro/` dirige o app num Android conectado pelo roteiro
inteiro da apresentação, na ordem da narração. Você só grava a tela.

```bash
DEMO_ACCOUNTS_PASSWORD='...' make demo
make demo DEMO_ACCOUNTS_PASSWORD='...' ARGS="--skip-build --pausa 3"
```

A senha é a mesma das contas de demonstração
([`back-end/demo-accounts.md`](back-end/demo-accounts.md)) e nunca fica no
código. Ela também é a senha da Ana criada a cada execução.

Precisa do `uv`: o alvo instala o `uiautomator2` num ambiente à parte. Ele
sobe um agente no aparelho (`/data/local/tmp/u2.jar`) que lê a tela em
~0,2s, contra ~2,2s do `uiautomator dump` do Android — o roteiro lê a tela
centenas de vezes, e só essa troca levou a execução de ~15 para ~5 min. O
script para o agente ao terminar, inclusive quando uma cena falha.

## O que acontece

**Preparo** (antes de gravar):

1. Confere o backend: o gateway responde, o catálogo tem
   `LM-MESA-120` e `LM-MESA-90` com estoque, Genética Básica tem 12
   questões. Avisa se o pagamento automático ou o avanço automático
   estiverem desligados no commerce. O script **não** sobe o stack.
2. Garante as contas `separador@`, `entregador@` e `admin@demo.edu`,
   **de forma idempotente**: tenta entrar com cada uma; as que entram são
   ignoradas. Só se faltar alguma roda o seed
   `app.seeds.demo_accounts`, que também é idempotente.
3. Lê o gabarito de Genética Básica no banco (só leitura), para acertar
   Leis de Mendel e errar Herança de propósito.
4. Prepara o aparelho: `adb reverse` da porta do gateway, compila e
   instala o APK com `DEMO_MULTI_SESSAO=true` (pule com `--skip-build`),
   **apaga os dados do app** (nenhuma sessão de gravação anterior aparece),
   concede a permissão de notificação, tira o app da economia de bateria,
   mantém a tela ligada no USB e avisa se o "Não perturbar" estiver ligado.
5. Entra uma vez com cada conta de staff pela tela, para o app guardar os
   atalhos de troca de perfil.
6. Espera Enter para começar (pule com `--sem-pausa`).

**Roteiro gravado** (~5 min com as opções padrão; o log mostra quanto cada cena levou):

| Cena | O que aparece |
|---|---|
| cadastro | A Ana se cadastra com e-mail novo (`ana.<data-hora>@example.com`) |
| onboarding | "Medicina pelo ENEM", prova no próximo 8 de novembro |
| roadmap | Checklist por matéria até a data |
| questionario | Biologia → Genética Básica, 12 questões |
| relatorio | Domínio por subtema, mensagem do tutor IA, recomendações |
| loja_e_compra | Parceiros Leroy Merlin, mesa de 120 cm, carrinho, endereço, PIX |
| separador_reporta_falta | Separador inicia e reporta falta; a gaveta mostra o push da Ana |
| aluna_escolhe_substituto | Ana escolhe a mesa compacta sugerida pela IA |
| separador_finaliza | Separador conclui com o item novo |
| entregador_coleta | Coleta cria o carregamento da frota própria sozinho |
| aluna_acompanha | Rastreio e mapa com o entregador andando |
| entregador_entrega | Entrega confirmada; a gaveta mostra o push |
| painel_admin | Relatório executivo com IA e painel analítico |

## Opções

| Opção | Efeito |
|---|---|
| `--skip-build` | Reaproveita o APK instalado |
| `--pausa N` | Segundos de respiro para a narração entre os passos (padrão 1) |
| `--sem-pausa` | Não espera Enter antes do roteiro gravado |
| `--segundos-de-mapa N` | Tempo mostrando o mapa (padrão 10) |

## Antes de gravar

- Celular desbloqueado, conectado por USB com depuração autorizada, rotação
  travada em retrato.
- Desligue o "Não perturbar" e limpe as notificações pessoais — a gaveta
  aparece duas vezes na gravação.
- Stack de pé com os seeds aplicados: `make services-seed` e o seed de
  Genética (ver [`back-end/study-tracker.md`](back-end/study-tracker.md)).

## Quando falha

O script para na cena que falhou e salva o print e a árvore de elementos da
tela em `/tmp/edu-demo-<data-hora>/`. O avanço automático do commerce move
um pedido parado há mais de 3 minutos: se uma execução ficar travada nesse
tempo, o pedido pode seguir sozinho — rode de novo, que tudo é recriado.

## Limites conhecidos

- `adb shell input text` não digita acento. Por isso o endereço da compra é
  em Barueri, sem acento nenhum; o script recusa texto não ASCII.
- O painel web (`web-admin/`) não faz parte do roteiro; o painel mostrado é
  o do admin no próprio app.

## Testes

```bash
make demo-test
```

Cobrem a leitura da árvore do `uiautomator` (só o app, com os limites
cortados pela área visível), a busca na tela lida, o escape de texto para o
`adb`, a data de novembro, a escolha da alternativa pelo gabarito e a
criação idempotente das contas.
