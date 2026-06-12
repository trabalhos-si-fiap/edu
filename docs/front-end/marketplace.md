# Módulo Marketplace (Flutter)

Documentação do módulo de marketplace do app **Edu IA** — loja, detalhe de
produto, carrinho e pagamento.

> Origem: as telas foram **migradas do projeto Kotlin/Compose `edu-kt`**. No
> Kotlin os dados vinham de microsserviços via Retrofit + ViewModels; no Flutter
> a UI e as interações foram reproduzidas fielmente, porém com **dados mockados**
> em memória (sem camada de rede ainda).

---

## 1. Visão geral

O módulo cobre o fluxo de compra completo:

```
Marketplace ──► Detalhe do Produto ──► Checkout (carrinho + endereço + pagamento)
     │                  │                        │
     └──── + Carrinho ──┴───── + Carrinho ───────┘ (badge do carrinho atualiza em tempo real)
                                                    │
                                                    └──► Adicionar/Editar Método de Pagamento
```

Seguindo a estrutura do `edu-kt`, **carrinho e pagamento vivem juntos na tela de
Checkout**; a gestão de métodos de pagamento fica em uma tela separada.

---

## 2. Estrutura de arquivos

O módulo é *feature-first* e se distribui por quatro features, espelhando os
domínios do Kotlin:

```
lib/
├── core/
│   └── utils/
│       └── currency.dart                  # formatBRL(double) -> "R$ 1.234,56"
├── features/
│   ├── marketplace/
│   │   ├── domain/
│   │   │   └── product.dart               # Product, Review
│   │   ├── data/
│   │   │   └── mock_marketplace.dart      # catálogo + reviews mockados + helpers
│   │   └── presentation/
│   │       ├── marketplace_screen.dart        # loja: busca, chips, grid
│   │       ├── product_detail_screen.dart     # detalhe do produto
│   │       ├── checkout_screen.dart           # carrinho + endereço + pagamento
│   │       ├── add_payment_method_screen.dart # adicionar/editar método
│   │       └── widgets/
│   │           ├── rating_stars.dart          # estrelas (com meia estrela)
│   │           ├── add_to_cart_button.dart    # botão animado "+ Carrinho"
│   │           ├── review_item.dart           # card de avaliação + bottom sheet
│   │           └── product_visuals.dart       # ícone/cores por tipo de produto
│   ├── cart/
│   │   ├── domain/
│   │   │   └── cart_item.dart              # CartItem
│   │   └── data/
│   │       └── cart_store.dart             # CartStore (ChangeNotifier via provider)
│   ├── payment/
│   │   ├── domain/
│   │   │   └── payment_method.dart         # PaymentMethod, PaymentMethodType, brandFromNumber
│   │   └── data/
│   │       └── payment_store.dart          # PaymentStore (ChangeNotifier via provider)
│   └── profile/
│       ├── domain/
│       │   └── address.dart               # Address (+ summary)
│       └── data/
│           └── mock_addresses.dart        # endereços mockados
```

---

## 3. Modelo de dados

| Tipo | Arquivo | Campos principais |
|------|---------|-------------------|
| `Product` | `marketplace/domain/product.dart` | `id`, `name`, `type`, `subtype`, `description`, `price` (`double`), `imageUrl`, `ratingAvg`, `ratingCount`; getter `categoryLabel` |
| `Review` | `marketplace/domain/product.dart` | `id`, `author`, `rating`, `comment`, `createdAt` |
| `CartItem` | `cart/domain/cart_item.dart` | `product`, `quantity`; getters `price`, `subtotal`; `copyWith` |
| `PaymentMethod` | `payment/domain/payment_method.dart` | `id`, `type`, `isDefault`, `cardLast4`, `cardBrand`, `cardholderName`, `cardExpiry` (MMYY), `cardholderTaxId`, `pixKey` |
| `PaymentMethodType` | `payment/domain/payment_method.dart` | `creditCard`, `pix`, `boleto` |
| `Address` | `profile/domain/address.dart` | `id`, `label`, `zipCode`, `street`, `number`, `complement`, `neighborhood`, `city`, `state`, `isFavorite`; getter `summary` |

> **Diferença em relação ao Kotlin:** lá `Product.price` era `String` (vinda da
> API). Aqui é `double` para permitir o cálculo de subtotais/totais no carrinho
> a partir de dados locais.

`brandFromNumber(digits)` deduz a bandeira pelo primeiro dígito do cartão
(`4`→Visa, `5`→Mastercard, `3`→Amex, `6`→Elo, senão "Cartão").

---

## 4. Gerência de estado

O projeto usa o pacote **[`provider`](https://pub.dev/packages/provider)** para
gerência de estado. O estado compartilhado é exposto como `ChangeNotifier`
registrado no topo da árvore (`MultiProvider` em `main.dart`) e consumido pelas
telas com `context.watch` (rebuild reativo) e `context.read` (ações, sem
subscrição). Isso substitui os `ViewModel`s singleton do `edu-kt`.

```dart
// main.dart — registro único na raiz
MultiProvider(
  providers: [
    ChangeNotifierProvider(create: (_) => CartStore()),
    ChangeNotifierProvider(create: (_) => PaymentStore()),
  ],
  child: MaterialApp(...),
);
```

> Convenção: as stores **não** são mais singletons (`.instance` foi removido).
> A instância vive na árvore e é obtida via `context`. `watch` só em métodos
> `build`; `read` em callbacks/handlers de eventos.

### `CartStore` (`cart/data/cart_store.dart`)

Obtido via `context.watch<CartStore>()` / `context.read<CartStore>()`.

| Membro | Descrição |
|--------|-----------|
| `items` | lista imutável dos itens |
| `isEmpty`, `totalQuantity`, `total` | derivados (total = soma dos subtotais) |
| `add(product, [qty])` | adiciona ou incrementa a quantidade |
| `decrement(productId)` | remove 1 unidade; remove o item ao chegar a 0 |
| `removeAll(productId)` | remove o produto inteiro |
| `clear()` | esvazia o carrinho (usado ao finalizar pedido) |

### `PaymentStore` (`payment/data/payment_store.dart`)

Obtido via `context.watch<PaymentStore>()` / `context.read<PaymentStore>()`.
Começa **semeado** com um cartão Visa padrão (para o checkout ter algo
selecionável). Sem persistência — estado só em memória.

| Membro | Descrição |
|--------|-----------|
| `methods` | lista imutável dos métodos |
| `byId(id)` | busca por id |
| `add(method, {makeDefault})` | gera id, adiciona; vira padrão se `makeDefault` ou se for o primeiro |
| `update(method, {makeDefault})` | atualiza método existente |
| `delete(id)` | remove; promove outro a padrão se o removido era o padrão |
| `setDefault(id)` | define o padrão exclusivo |

**Padrão de consumo nas telas:**

```dart
// Leitura reativa (rebuild quando o store notifica):
final count = context.watch<CartStore>().totalQuantity;
Text('$count');

// Checkout observa os dois stores ao mesmo tempo:
final cart = context.watch<CartStore>();
final methods = context.watch<PaymentStore>().methods;

// Ações (em callbacks) usam read — não cria subscrição:
onPressed: () => context.read<CartStore>().add(product),
```

---

## 5. Telas e rotas

| Rota | Tela | Argumentos | Descrição |
|------|------|------------|-----------|
| `/marketplace` | `MarketplaceScreen` | — | Loja: busca, chips de categoria, grid 2 colunas |
| `/product` | `ProductDetailScreen` | `int productId` | Detalhe: hero, rating, preço, descrição, avaliações |
| `/checkout` | `CheckoutScreen` | — | Carrinho + endereço + métodos de pagamento + finalização |
| `/add-payment-method` | `AddPaymentMethodScreen` | `String? methodId` | Adiciona (sem arg) ou edita (com id) um método |

Argumentos chegam via `ModalRoute.of(context)!.settings.arguments` e são passados
com `Navigator.pushNamed(context, rota, arguments: ...)`.

### Marketplace
- Top bar: perfil + campo de busca + ícone de carrinho com **badge** reativo.
- Chips de categoria (`Tudo` + tipos distintos do catálogo) filtram por `type`.
- Busca filtra por `name`/`description` (case-insensitive); combina com a categoria.
- Grid de cards (`SliverGrid` com `mainAxisExtent` calculado por `LayoutBuilder`
  para evitar overflow em qualquer largura). Rating e preço usam `FittedBox`
  (`scaleDown`) para nunca estourar em telas estreitas.
- Card → abre o detalhe; estrelas → bottom sheet de avaliações; "+ Carrinho" → `CartStore.add`.

### Detalhe do produto
- Hero image (placeholder por tipo), tag de categoria, card com nome + rating + preço,
  card "Sobre o produto", lista de avaliações.
- Barra inferior fixa "Adicionar ao carrinho" (azul). Badge do carrinho na AppBar.

### Checkout
- **Carrinho:** cards com stepper de quantidade (− vermelho / + roxo), subtotal por
  item, botão X (remover tudo) e linha de **Total**. Estado vazio tratado.
- **Endereço:** cards selecionáveis; pré-seleciona o favorito (ou o primeiro).
- **Pagamento:** cards selecionáveis com ações estrela (padrão) / editar / excluir,
  + botão tracejado "Outro método". Seleção efetiva cai no padrão se o selecionado
  sumir (ex.: após exclusão).
- **Finalizar:** diálogo de confirmação → limpa o carrinho e:
  - **Cartão** → snackbar de sucesso + volta;
  - **PIX/Boleto** → diálogo com código copiável (copia/cola PIX ou linha
    digitável do boleto, gerados localmente).

### Adicionar/Editar método de pagamento
- Seletor de tipo (Cartão / PIX / Boleto).
- Cartão: número (máscara `0000 0000 0000 0000`), nome, validade (`MM/AA`), CVV,
  e **CPF/CNPJ** (máscara progressiva). PIX/Boleto exibem caixa informativa.
- Em modo edição, prefilla os campos e o número pode ficar em branco (mantém o
  cartão atual). Validação portada de `validateCreditCardForm` do Kotlin.
- Salvar persiste no `PaymentStore` (add/update) com opção "definir como padrão".

---

## 6. Componentes compartilhados (`presentation/widgets/`)

| Componente | Descrição |
|------------|-----------|
| `RatingStars` | 5 estrelas com suporte a meia estrela; label opcional `"4.5 (128)"` |
| `AddToCartButton` | Botão que vira "Adicionado" com check por 1,2s (escala + fade) |
| `ReviewItem` + `showReviewsBottomSheet` | Card de avaliação e bottom sheet de reviews do produto |
| `product_visuals.dart` | `iconForProduct(type)` e `categoryColorsFor(type)` (apostila/digital → roxo; demais → verde) |

---

## 7. Dados mockados

- `mock_marketplace.dart`: 6 produtos + reviews por id; helpers `productById(id)`,
  `reviewsForProduct(id)`.
- `mock_addresses.dart`: 2 endereços (1 favorito).
- `PaymentStore`: semeado com 1 cartão Visa padrão.

### Como trocar por API no futuro
A camada de domínio já está isolada. Para integrar ao BFF basta:
1. Criar repositórios (`marketplace/data/...`) que retornem os mesmos tipos de
   domínio a partir de HTTP.
2. Substituir as leituras diretas das constantes mock por chamadas assíncronas
   (e tratar estados de loading/erro, como no `edu-kt`).
3. Manter os `Store`s como cache/estado de sessão, populados pelos repositórios.

---

## 8. Design system aplicado

Cores migradas do `EduColors` para `AppColors`
(`core/theme/app_colors.dart`): `purple`, `purpleSoft`, `greenSoft`, `greenDark`,
`danger`, `star` (`#F59E0B`), `imagePlaceholder`, `cartImageBlue`. Todas as telas
usam o `AppColors.headerGradient` como fundo, com `Scaffold` transparente — padrão
do projeto. Cards `borderRadius` 16–20 com sombra sutil; botões primários roxos
`borderRadius` 12.

Ver também: [Arquitetura](archtecture.md) · [Guia Visual](visual_guide.md).
