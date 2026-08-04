# Edu IA - Frontend Flutter

App mobile educacional construido com Flutter, parte do ecossistema Edu IA.

## Como Rodar

Resumo: **(1)** instale o toolchain, **(2)** suba o backend, **(3)** gere a
config do Firebase, **(4)** rode o app apontando o `API_BASE_URL` certo para a
sua plataforma. Os passos abaixo detalham cada um.

### 1. Pré-requisitos

| Ferramenta | Para quê | Como |
|---|---|---|
| **Flutter SDK** | Build do app (todas as plataformas) | <https://flutter.dev/setup> — depois rode `flutter doctor` |
| **Docker + Docker Compose** | Backend local (API, Postgres, Redis, RabbitMQ) | <https://docs.docker.com/get-docker/> |
| **Firebase/FlutterFire CLI** | Notificações push (FCM) | Veja [firebase_setup.md](../docs/front-end/firebase_setup.md) |
| Xcode + CocoaPods | Rodar no **iOS/macOS** (apenas macOS) | `xcode-select --install`; `sudo gem install cocoapods` |
| Android SDK / Android Studio | Rodar no **Android** | Vem com o Android Studio; `flutter doctor` valida |

Rode `flutter doctor` e resolva o que estiver marcado antes de continuar.

```bash
cd front-end-flutter
flutter pub get          # baixa as dependências do pubspec
```

### 2. Suba o backend

O app precisa da API rodando. Na raiz do repositório:

```bash
make back-up             # sobe postgres, redis, rabbitmq, api, worker
make back-migrate        # aplica as migrações do banco (primeira vez)
make back-seed           # (opcional) popula o catálogo de produtos
```

A API fica publicada na porta `API_PORT_EXTERNAL` do `back-end/.env` — hoje
**8001** (`http://localhost:8001`). Confira os logs com `make back-logs`.

> O app continua falando com o monolito. O stack de microserviços sobe ao lado
> dele (`make stack-up`, gateway em `:8100`) e ainda não serve o app — veja
> [microservices.md](../docs/back-end/microservices.md).

### 3. Configure o Firebase

A config do Firebase (com API keys) **não é versionada** — gere a sua antes do
primeiro run. Resumo:

```bash
cd front-end-flutter
flutterfire configure --platforms=android,ios,macos
```

Passo a passo completo, alternativa manual e templates `*.example` em
[firebase_setup.md](../docs/front-end/firebase_setup.md).

### 4. Rode o app

⚠️ **O endereço da API muda por plataforma.** Passe o endereço certo via
`--dart-define=API_BASE_URL=...`, ou use `make front`, que monta a URL sozinho
lendo a porta do `back-end/.env`:

| Plataforma | API_BASE_URL | Comando |
|---|---|---|
| **Emulador Android** | `http://10.0.2.2:8001/api` | `make front` ou `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001/api` |
| **Simulador iOS** | `http://localhost:8001/api` | `flutter run -d <sim> --dart-define=API_BASE_URL=http://localhost:8001/api` |
| **Dispositivo físico (Wi-Fi)** | `http://SEU_IP_LAN:8001/api` | `make front` (auto-detecta o IP da LAN) |
| **Dispositivo USB (Android)** | `http://localhost:8001/api` via `adb reverse` | `make front-device` |
| **Chrome / Web** | `http://localhost:8001/api` | `flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8001/api` |
| **Desktop (macOS/Linux)** | `http://localhost:8001/api` | `flutter run -d macos` / `make front-linux` |

> ⚠️ **O default embutido no código está desatualizado.** O
> `ApiConfig.baseUrl` ([api_config.dart](lib/core/network/api_config.dart))
> ainda aponta para `http://10.0.2.2:8000/api`, de quando a API era publicada
> na 8000. Um `flutter run` **sem** `--dart-define` bate na porta errada. Use
> `make front` (que passa a porta certa) ou passe o `--dart-define` na mão.
>
> A porta tem que bater com a `API_PORT_EXTERNAL` do `back-end/.env` — **8001**
> nesta máquina. Guia detalhado de iOS (simulador, device, troubleshooting):
> [running_ios.md](../docs/front-end/running_ios.md).

#### Atalhos do Makefile (raiz do projeto)

```bash
make front            # roda em device/emulador (auto-detecta IP da LAN p/ Wi-Fi)
make front-device     # roda em celular USB (adb reverse → localhost:8001)
make front-web        # roda no Chrome
make front-linux      # roda no Linux desktop
make front-devices    # lista devices/emuladores disponíveis
make front-analyze    # análise estática (flutter analyze)
make front-test       # testes (flutter test)
make front-clean      # limpa artefatos de build
```

Para escolher um device específico manualmente: `flutter devices` lista os ids,
e `flutter run -d <id>` seleciona um.

### Troubleshooting rápido

| Sintoma | Causa | Correção |
|---|---|---|
| "Não foi possível conectar ao servidor" no login/cadastro | `API_BASE_URL` errado para a plataforma | Use a tabela acima; confirme `make back-up` |
| App não abre a Home após login | (corrigido) push token bloqueava a navegação | `syncToken()` é best-effort — veja [messaging_service.dart](lib/features/notifications/data/messaging_service.dart) |
| Erro de build: `firebase_options.dart` não encontrado | Firebase não configurado | Rode `flutterfire configure` — [firebase_setup.md](../docs/front-end/firebase_setup.md) |
| `APNS token has not been received` (iOS) | Simulador iOS não tem APNS | Esperado e ignorado; use device físico para push real |
| Erros de CocoaPods (iOS/macOS) | CocoaPods ausente/desatualizado | `sudo gem install cocoapods`; `cd ios && pod install` |

## Estrutura do Projeto

```
lib/
├── core/
│   └── theme/
│       ├── app_colors.dart       # Paleta de cores e gradientes
│       └── app_theme.dart        # ThemeData global (inputs, botoes)
├── features/
│   ├── auth/
│   │   └── presentation/
│   │       ├── login_screen.dart            # Tela de login Edu
│   │       ├── logistics_login_screen.dart  # Tela de login Edu Logistics
│   │       └── register_screen.dart         # Tela de cadastro
│   ├── home/
│   │   └── presentation/
│   │       └── home_screen.dart      # Dashboard principal
│   ├── marketplace/
│   │   └── presentation/
│   │       ├── marketplace_screen.dart         # Loja: busca, chips, grid de produtos
│   │       ├── product_detail_screen.dart      # Detalhe do produto + avaliacoes
│   │       ├── checkout_screen.dart            # Carrinho + endereco + pagamento
│   │       ├── add_payment_method_screen.dart  # Adicionar/editar metodo de pagamento
│   │       ├── orders_screen.dart              # Lista de pedidos do usuario
│   │       └── order_details_screen.dart       # Status do rastreio + suporte
│   ├── logistics/
│   │   └── presentation/
│   │       ├── logistics_dashboard_screen.dart # Painel de logistica pos-login
│   │       └── order_picking_screen.dart       # Separacao de pedido na rota
│   ├── notifications/
│   │   ├── data/
│   │   │   ├── messaging_service.dart   # Ciclo FCM: permissao, token, foreground
│   │   │   └── notifications_api.dart   # Registro de device + GET /notifications
│   │   ├── domain/
│   │   │   └── notification_model.dart  # Modelo da notificacao
│   │   └── presentation/
│   │       └── notifications_screen.dart # Historico real (loading/erro/vazio + pull-to-refresh)
│   └── profile/
│       └── presentation/
│           └── profile_screen.dart   # Perfil do usuario
└── main.dart                         # Entry point + rotas
```

## Telas Implementadas

| Rota | Tela | Descricao |
|------|------|-----------|
| `/login` | LoginScreen | Email + senha, login social, link para Edu Logistics |
| `/logistics` | LogisticsLoginScreen | Login do Edu Logistics com seletor de papel |
| `/register` | RegisterScreen | Cadastro com validacao de senha |
| `/home` | HomeScreen | Dashboard com progresso, trilhas, revisao |
| `/profile` | ProfileScreen | Perfil, stats, configuracoes, logout |
| `/marketplace` | MarketplaceScreen | Loja com busca, chips de categoria e grid de produtos |
| `/product` | ProductDetailScreen | Detalhe do produto: hero, rating, preco, descricao, avaliacoes |
| `/checkout` | CheckoutScreen | Carrinho (stepper + total), endereco e metodos de pagamento |
| `/add-payment-method` | AddPaymentMethodScreen | Cadastro/edicao de cartao, PIX ou boleto |
| `/orders` | OrdersScreen | Pedido ativo com stepper de entrega + historico |
| `/order-details` | OrderDetailsScreen | Status do rastreio, localizacao, conteudo do kit |
| `/notifications` | NotificationsScreen | Historico de notificacoes (GET /notifications); icone por `data.type` (ex.: entrega) |
| `/logistics-dashboard` | LogisticsDashboardScreen | Painel de logistica com destino atual, progresso do dia e proximas paradas |
| `/logistics-picking` | OrderPickingScreen | Separacao de pedido com item atual, proximos na rota e info de envio |

## Design System

### Cores

| Nome | Hex | Uso |
|------|-----|-----|
| `purple` | `#5B00DF` | Cor primaria, links, botoes destaque |
| `blue` | `#369FFF` | Cards de features |
| `background` | `#A9CADD` | Fundo gradiente das telas |
| `primary` | `#1A1A2E` | Texto principal, botao Entrar |
| `textSecondary` | `#6B7280` | Texto secundario |
| `white` | `#FFFFFF` | Cards, fundo do footer |

### Gradiente

Todas as telas usam o gradiente `AppColors.headerGradient` como background, aplicado em um `Container` que envolve o `Scaffold` com `backgroundColor: Colors.transparent`.

### Componentes Padrao

- **Cards**: `borderRadius: 24`, fundo branco, `boxShadow` sutil
- **Footer (BottomNavigationBar)**: fundo branco, `borderRadius: 24` no topo via `ClipRRect`
- **Inputs**: `borderRadius: 12`, preenchimento cinza, sem borda
- **Botoes**: `borderRadius: 12`, fundo escuro (`primary`)

## Assets

```
assets/
├── images/
│   ├── brain.png
│   ├── calendar.png
│   ├── checklist.png
│   ├── clock.png
│   ├── target.png
│   └── subjects/          # Icones das materias (512x512 PNG)
│       ├── icon_biologia.png
│       ├── matematica.png
│       ├── geografia.png
│       ├── historia.png
│       └── ...
```

> **Nota sobre SVGs**: Os icones de subjects foram convertidos de SVG para PNG porque os SVGs originais continham imagens PNG embutidas em base64, que o `flutter_svg` nao renderiza corretamente. Sempre verifique se o SVG usa vetores reais antes de adotar.

## Navegacao

Navegacao via `Navigator` com rotas nomeadas definidas em `main.dart`:

- Login -> Home: apos autenticacao valida
- Login <-> Cadastro: via bottom nav e links
- Login -> Logistics: link "Entrar no Edu Logistics" no rodape
- Home -> Profile: icone de perfil no topo
- Profile -> Orders: item "Meus pedidos" nas configuracoes
- Profile -> Intro: botao Logout (limpa stack)
- NavBar (Loja) -> Marketplace: indice 4 do bottom nav em todas as telas
- Marketplace -> Product: toque no card do produto
- Marketplace/Product -> Checkout: icone de carrinho na top bar
- Checkout -> AddPaymentMethod: opcao "Outro metodo" (ou icone editar para alterar)
- Orders -> OrderDetails: botao "Detalhes do pedido"
- Logistics (login) -> LogisticsDashboard: credenciais `teste` / `teste`
- LogisticsDashboard -> OrderPicking: aba "Separacao" no bottom nav

## Documentacao Adicional

- [Arquitetura e Guidelines](../docs/front-end/archtecture.md) -- Padroes de codigo, arquitetura feature-first, convencoes
- [Guia de Estilo Visual](../docs/front-end/visual_guide.md) -- Padroes de UI, componentes reutilizaveis, layout
- [Modulo Marketplace](../docs/front-end/marketplace.md) -- Loja, produto, carrinho e pagamento (modelos, stores, telas)
- [Setup do Firebase](../docs/front-end/firebase_setup.md) -- Config do FCM, templates `*.example`, chaves fora do git
- [Rodando no iOS](../docs/front-end/running_ios.md) -- Simulador/device, `API_BASE_URL` por plataforma, troubleshooting

## Dependencias

- `flutter` (SDK)
- `cupertino_icons` -- Icones iOS
- `provider` -- gerencia de estado (ChangeNotifier compartilhado via MultiProvider)
