# Guia de Estilo Visual - Edu IA

Referencia visual para manter consistencia entre todas as telas do app.

## 1. Layout Base

Todas as telas seguem o mesmo padrao de layout:

```dart
Container(
  decoration: const BoxDecoration(gradient: AppColors.headerGradient),
  child: Scaffold(
    backgroundColor: Colors.transparent,
    body: /* conteudo */,
    bottomNavigationBar: ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      child: BottomNavigationBar(
        backgroundColor: AppColors.white,
        // ...
      ),
    ),
  ),
)
```

**Por que?** O gradiente precisa cobrir toda a tela, inclusive atras do footer. O `Scaffold` fica transparente para que o gradiente apareca nos cantos arredondados do `BottomNavigationBar`.

## 2. Paleta de Cores

Definidas em `core/theme/app_colors.dart`:

| Token | Hex | Onde usar |
|-------|-----|-----------|
| `purple` | `#5B00DF` | Links, badges, botoes de destaque, barra de progresso |
| `blue` | `#369FFF` | Cards de features (Pomodoro, Identificar lacunas) |
| `primary` | `#1A1A2E` | Texto titulo, botao "Entrar", fundo do card escuro |
| `background` | `#A9CADD` | Base do gradiente |
| `textPrimary` | `#1A1A2E` | Titulos e texto principal |
| `textSecondary` | `#6B7280` | Subtitulos, hints, labels secundarios |
| `inputFill` | `#F3F4F6` | Fundo dos campos de input |
| `inputBorder` | `#E5E7EB` | Bordas dos botoes sociais, dividers |
| `white` | `#FFFFFF` | Cards, footer, fundo de inputs |

### Cores extras usadas pontualmente

| Hex | Onde |
|-----|------|
| `#9645D1` | Cards "Area de conteudos" e "Agenda" |
| `#4B5563` | Texto descritivo na tela de cadastro (cinza mais forte) |
| `#B0B0C0` | Texto do card "Revisao de Ciclo" (fundo escuro) |
| `#2A2A3E` | Container da imagem do cerebro |
| `#2A2A4A` | Borda do card "Revisao de Ciclo" |

## 3. Tipografia

Fonte padrao: **Roboto** (via `ThemeData.fontFamily`).

| Elemento | Tamanho | Peso | Cor |
|----------|---------|------|-----|
| Titulo grande (Bem vindo) | 28-32 | w800 | textPrimary |
| Titulo de secao (Suas Trilhas) | 24 | w800 | textPrimary |
| Titulo de card | 22 | w800 | white ou textPrimary |
| Label de campo | 14 | w600 | textPrimary |
| Texto de corpo | 14 | normal | textSecondary |
| Label pequeno (PROGRESSO ATUAL) | 12 | w700 | purple |
| Badge (LEVEL 18) | 12 | w700 | white |

## 4. Componentes

### Cards

```
Border radius: 24
Fundo: branco
Shadow: color black 6%, blur 16, offset (0, 4)
Padding interno: 20-24
```

Variantes:
- **Card branco** (progresso, trilhas, perfil): fundo `AppColors.white`
- **Card colorido** (features): fundo com cor solida, texto branco
- **Card escuro** (revisao de ciclo): fundo `#1A1A2E`, borda `#2A2A4A`

### Botoes

**Primario (ElevatedButton)**:
- Fundo: `AppColors.primary` (#1A1A2E)
- Texto: branco, 16, w600
- Border radius: 12
- Largura total (`double.infinity`)

**Destaque (ex: Revisar Agora)**:
- Fundo: `AppColors.purple`
- Border radius: 24 (mais arredondado)
- Largura auto (nao full-width)

**Social (OutlinedButton)**:
- Borda: `AppColors.inputBorder`
- Border radius: 12
- Texto: `AppColors.textPrimary`

### Inputs

Definidos globalmente em `app_theme.dart`:
- Filled: true, cor `AppColors.inputFill`
- Border radius: 12
- Sem borda visivel (ativa borda roxa no focus)
- Padding: horizontal 20, vertical 16

### Footer (BottomNavigationBar)

- Background: branco
- Border radius topo: 24 (via `ClipRRect`)
- Cor selecionado: `AppColors.purple`
- Cor nao selecionado: `AppColors.textSecondary`
- Tipo: `BottomNavigationBarType.fixed` (para 5+ items)

### Divider com texto

```dart
Row(
  children: [
    Expanded(child: Divider()),
    Padding(child: Text('Ou entre com')),
    Expanded(child: Divider()),
  ],
)
```

## 5. Espacamento

| Contexto | Valor |
|----------|-------|
| Padding lateral das telas | 20 |
| Padding lateral dos cards de auth | 16 (margin) + 24 (padding interno) |
| Gap entre cards | 16 |
| Gap entre secoes | 24 |
| Gap label -> input | 8 |
| Gap entre inputs | 20 |
| SafeArea top (telas sem AppBar) | via `SafeArea` |
| Header auth (top padding) | 60 |

## 6. Imagens e Assets

- Formato: **PNG** (512x512 para icones de materias)
- Usar `filterQuality: FilterQuality.high` para PNGs pequenos renderizados em tamanho reduzido
- Evitar SVGs que contenham imagens rasterizadas embutidas
- Assets declarados em `pubspec.yaml` por pasta

## 7. Padroes de Widget

### Tela com gradiente + footer

Toda tela nova deve seguir:

1. `Container` com gradiente envolvendo o `Scaffold`
2. `Scaffold.backgroundColor = Colors.transparent`
3. `BottomNavigationBar` dentro de `ClipRRect` com radius 24

### Cards como widgets privados

Extrair widgets complexos como classes `_NomeWidget` privadas no mesmo arquivo. Manter cada arquivo abaixo de 250 linhas quando possivel.

### Callbacks para acoes

Widgets filhos recebem `VoidCallback` para acoes (login, navegacao). A logica fica no widget pai (`State`).
