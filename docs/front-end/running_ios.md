# Rodando o app no iOS (simulador e dispositivo)

Guia para rodar o frontend Flutter no iOS. Não há credencial a configurar
antes do primeiro run: a spec A tirou o Firebase do app.

## Pré-requisitos

- macOS com **Xcode** instalado (`xcode-select --install` para as ferramentas de
  linha de comando).
- **CocoaPods**: `sudo gem install cocoapods`.
- **Flutter** no PATH (`flutter doctor` deve passar em icons toolchain e Xcode).
- Backend rodando localmente (`make stack-up`) — veja
  [back-end/microservices](../back-end/microservices.md).

## A pegadinha do endereço da API

O `baseUrl` padrão do app
([api_config.dart](../../front-end-flutter/lib/core/network/api_config.dart))
aponta para `http://10.0.2.2:8100/api` — o **API gateway** dos microsserviços,
não um monolito. O `10.0.2.2` é o alias **do emulador Android** para a máquina
host. **No simulador iOS esse alias não existe** — o simulador compartilha a
rede do host, então use `localhost`.

Sempre passe o endereço certo via `--dart-define`:

| Alvo | API_BASE_URL |
|---|---|
| Simulador iOS | `http://localhost:8100/api` |
| Emulador Android | `http://10.0.2.2:8100/api` |
| Dispositivo físico (mesma Wi-Fi) | `http://SEU_IP_LAN:8100/api` |

> A porta é a `GATEWAY_PORT_EXTERNAL` do `back-end/.env` — **8100** hoje, a
> mesma publicada pelo `docker-compose` e a mesma do default do
> `api_config.dart`. O que muda entre alvos é o **host**, não a porta:
> `flutter run` sem `--dart-define` só acerta no emulador Android. `make front`
> monta a URL a partir do `back-end/.env` e acerta em qualquer alvo.

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
  --dart-define=API_BASE_URL=http://localhost:8100/api
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
  --dart-define=API_BASE_URL=http://SEU_IP_LAN:8100/api
```

Descubra seu IP da LAN com `ipconfig getifaddr en0`. O gateway já escuta em
`0.0.0.0:8000` dentro do container, publicado na **8100** do host; garanta que o celular está na mesma Wi-Fi.

## Notificações no simulador

O simulador iOS **não recebe token APNS**, então o registro de push é pulado
(você verá `MessagingService.syncToken skipped: ...` no log) — isso é esperado
e **não impede** login/cadastro nem a navegação. Para testar push real, use um
dispositivo físico.

## Troubleshooting

| Sintoma | Causa provável | Correção |
|---|---|---|
| "Não foi possível conectar ao servidor" no login/cadastro | API_BASE_URL errado (porta/host) | Use `--dart-define=API_BASE_URL=http://localhost:8100/api` e confira `make stack-up` |
| App trava após login (não abre a Home) | exceção não tratada no pós-login | Já corrigido: `syncToken()` é best-effort. Veja [messaging_service.dart](../../front-end-flutter/lib/features/notifications/data/messaging_service.dart) |
| `APNS token has not been received` | simulador iOS sem APNS | Esperado; ignorado pelo app. Use device físico para push real |
| `CocoaPods not installed` / erros de pod | CocoaPods ausente/desatualizado | `sudo gem install cocoapods` e `cd ios && pod install` |
