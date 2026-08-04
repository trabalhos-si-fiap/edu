# Rodando o app no iOS (simulador e dispositivo)

Guia para rodar o frontend Flutter no iOS. Para a configuração do Firebase
(necessária antes do primeiro run), veja [firebase_setup.md](firebase_setup.md).

## Pré-requisitos

- macOS com **Xcode** instalado (`xcode-select --install` para as ferramentas de
  linha de comando).
- **CocoaPods**: `sudo gem install cocoapods`.
- **Flutter** no PATH (`flutter doctor` deve passar em icons toolchain e Xcode).
- Backend rodando localmente (`make back-up`) — veja
  [back-end/start-here](../back-end/start-here.md).
- Config do Firebase gerada — veja [firebase_setup.md](firebase_setup.md).

## A pegadinha do endereço da API

O `baseUrl` padrão do app
([api_config.dart](../../front-end-flutter/lib/core/network/api_config.dart))
aponta para `http://10.0.2.2:8000/api`, que é o alias **do emulador Android**
para a máquina host. **No simulador iOS esse alias não existe** — o simulador
compartilha a rede do host, então use `localhost`.

Sempre passe o endereço certo via `--dart-define`:

| Alvo | API_BASE_URL |
|---|---|
| Simulador iOS | `http://localhost:8001/api` |
| Emulador Android | `http://10.0.2.2:8001/api` |
| Dispositivo físico (mesma Wi-Fi) | `http://SEU_IP_LAN:8001/api` |

> A porta é a `API_PORT_EXTERNAL` do `back-end/.env` — **8001** hoje, a mesma
> publicada pelo `docker-compose`.
>
> ⚠️ O default embutido no `api_config.dart` continua sendo a **8000**, de
> quando a API era publicada nessa porta. Ele não foi atualizado, então
> `flutter run` sem `--dart-define` bate na porta errada em qualquer
> plataforma. `make front` monta a URL a partir do `back-end/.env` e acerta.

## Simulador iOS

```bash
# 1. Suba um simulador (ou abra pelo app Simulator)
open -a Simulator

# 2. Liste os devices e pegue o id do simulador iOS
cd front-end-flutter
flutter devices

# 3. Rode apontando para o backend via localhost
flutter run \
  -d "iPhone 16e" \
  --dart-define=API_BASE_URL=http://localhost:8001/api
```

Pode passar o nome do device (`-d "iPhone 16e"`) ou o UUID do `flutter devices`.

### Primeira execução

A primeira build roda `pod install` e compila via Xcode — leva alguns minutos.
Builds seguintes são incrementais e rápidas. Comandos úteis enquanto roda:
`r` (hot reload), `R` (hot restart), `q` (sair).

## Dispositivo iOS físico

Requer um time de assinatura configurado no Xcode
(`ios/Runner.xcworkspace` → Signing & Capabilities) e o device confiável.

```bash
flutter run \
  -d "<id-do-iphone>" \
  --dart-define=API_BASE_URL=http://SEU_IP_LAN:8001/api
```

Descubra seu IP da LAN com `ipconfig getifaddr en0`. O backend já escuta em
`0.0.0.0:8000` dentro do container, publicado na **8001** do host; garanta que o celular está na mesma Wi-Fi.

## Notificações no simulador

O simulador iOS **não recebe token APNS**, então o registro de push é pulado
(você verá `MessagingService.syncToken skipped: ...` no log) — isso é esperado
e **não impede** login/cadastro nem a navegação. Para testar push real, use um
dispositivo físico (veja [firebase_setup.md](firebase_setup.md)).

## Troubleshooting

| Sintoma | Causa provável | Correção |
|---|---|---|
| "Não foi possível conectar ao servidor" no login/cadastro | API_BASE_URL errado (porta/host) | Use `--dart-define=API_BASE_URL=http://localhost:8001/api` e confira `make back-up` |
| App trava após login (não abre a Home) | exceção não tratada no pós-login | Já corrigido: `syncToken()` é best-effort. Veja [messaging_service.dart](../../front-end-flutter/lib/features/notifications/data/messaging_service.dart) |
| `APNS token has not been received` | simulador iOS sem APNS | Esperado; ignorado pelo app. Use device físico para push real |
| Erro de build do Firebase / `firebase_options.dart` não encontrado | config não gerada | Rode `flutterfire configure` — veja [firebase_setup.md](firebase_setup.md) |
| `CocoaPods not installed` / erros de pod | CocoaPods ausente/desatualizado | `sudo gem install cocoapods` e `cd ios && pod install` |
