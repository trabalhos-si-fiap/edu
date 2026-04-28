# Edu IA - Frontend Flutter

App mobile educacional construido com Flutter, parte do ecossistema Edu IA.

## Quick Start

```bash
# Na raiz do projeto (estuda_app/)
make front            # roda no dispositivo padrao
make front-web        # roda no Chrome
make front-linux      # roda no Linux desktop
make front-analyze    # analise estatica
make front-test       # testes
make front-clean      # limpar build
```

Ou diretamente:

```bash
cd front-end-flutter
flutter run
```

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
│   │       ├── marketplace_screen.dart         # Loja com banner e produtos
│   │       ├── checkout_screen.dart            # Revisao do carrinho + pagamento
│   │       ├── add_payment_method_screen.dart  # Adicionar metodo de pagamento
│   │       ├── orders_screen.dart              # Lista de pedidos do usuario
│   │       └── order_details_screen.dart       # Status do rastreio + suporte
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
| `/marketplace` | MarketplaceScreen | Loja com banner de colecao em destaque e produtos |
| `/checkout` | CheckoutScreen | Revisao do carrinho e selecao de metodo de pagamento |
| `/add-payment-method` | AddPaymentMethodScreen | Cadastro de cartao, PIX ou boleto |
| `/orders` | OrdersScreen | Pedido ativo com stepper de entrega + historico |
| `/order-details` | OrderDetailsScreen | Status do rastreio, localizacao, conteudo do kit |

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
- Marketplace -> Checkout: icone de carrinho na top bar
- Checkout -> AddPaymentMethod: opcao "Outro metodo"
- Orders -> OrderDetails: botao "Detalhes do pedido"

## Documentacao Adicional

- [Arquitetura e Guidelines](docs/archtecture.md) -- Padroes de codigo, arquitetura feature-first, convencoes
- [Guia de Estilo Visual](docs/visual_guide.md) -- Padroes de UI, componentes reutilizaveis, layout

## Dependencias

- `flutter` (SDK)
- `cupertino_icons` -- Icones iOS
