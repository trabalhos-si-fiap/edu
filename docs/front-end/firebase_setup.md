# Firebase Setup (Flutter)

O app usa **Firebase Cloud Messaging (FCM)** para notificações push. A
configuração do Firebase é **por projeto** e contém API keys, então os arquivos
gerados **não são versionados** — cada desenvolvedor/ambiente gera os seus a
partir do seu próprio projeto Firebase.

Este guia mostra como configurar do zero. Para rodar o app depois, veja
[running_ios.md](running_ios.md).

## Arquivos gerados (NÃO versionados)

Estão no [.gitignore](../../.gitignore) porque carregam API keys ou config
específica do projeto. Para cada um há um template `*.example` versionado
mostrando a estrutura esperada:

| Arquivo (ignorado) | Template versionado | Contém |
|---|---|---|
| `lib/firebase_options.dart` | `lib/firebase_options.dart.example` | API keys de todas as plataformas |
| `android/app/google-services.json` | `android/app/google-services.json.example` | API key Android |
| `ios/Runner/GoogleService-Info.plist` | `ios/Runner/GoogleService-Info.plist.example` | API key iOS |
| `macos/Runner/GoogleService-Info.plist` | (usa o mesmo template do iOS) | API key macOS |
| `firebase.json` | — (gerado pelo CLI) | mapeia projeto → arquivos |

> ⚠️ **Nunca** commite os arquivos reais. Se um deles aparecer no `git status`
> como rastreado, pare e confira o `.gitignore`.

## Pré-requisitos

```bash
# 1. Firebase CLI (uma vez por máquina)
npm install -g firebase-tools
firebase login          # abre o navegador para autenticar

# 2. FlutterFire CLI (uma vez por máquina)
dart pub global activate flutterfire_cli
# garanta que ~/.pub-cache/bin está no PATH
```

## Configuração (recomendado: `flutterfire configure`)

A forma canônica — gera **todos** os arquivos acima de uma vez, com os valores
corretos do seu projeto:

```bash
cd front-end-flutter
flutterfire configure \
  --project=SEU_PROJECT_ID \
  --platforms=android,ios,macos
```

O CLI vai:
1. Listar/registrar os apps (bundle id iOS/macOS: `br.com.fiap.estudaApp`;
   package Android: `br.com.fiap.estuda_app`) no projeto Firebase.
2. Gerar `lib/firebase_options.dart`, `firebase.json`,
   `android/app/google-services.json` e os `GoogleService-Info.plist`.

Se for um projeto Firebase novo, crie-o antes em
<https://console.firebase.google.com> e habilite **Cloud Messaging**.

## Alternativa manual (a partir dos templates)

Sem o FlutterFire CLI, copie cada template e preencha com os valores do
console Firebase (Configurações do projeto → Seus apps):

```bash
cd front-end-flutter
cp lib/firebase_options.dart.example          lib/firebase_options.dart
cp android/app/google-services.json.example   android/app/google-services.json
cp ios/Runner/GoogleService-Info.plist.example   ios/Runner/GoogleService-Info.plist
cp ios/Runner/GoogleService-Info.plist.example   macos/Runner/GoogleService-Info.plist
```

Substitua os placeholders (`YOUR_*`, `your-project-id`) pelos valores reais.

## Como o app inicializa

Em [lib/main.dart](../../front-end-flutter/lib/main.dart):

```dart
await Firebase.initializeApp(
  options: DefaultFirebaseOptions.currentPlatform, // de firebase_options.dart
);
FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
```

O ciclo de vida do FCM (permissão, exibição em foreground, sync de token) fica em
[messaging_service.dart](../../front-end-flutter/lib/features/notifications/data/messaging_service.dart):
`init()` roda uma vez no startup; `syncToken()` registra o device no backend
após o login. O `syncToken()` é **best-effort** — falhas (ex.: simulador iOS sem
token APNS) são engolidas e nunca bloqueiam o fluxo de login/cadastro.

## iOS / macOS: push em simulador

O **simulador iOS não tem token APNS**, então `getToken()` lança
`apns-token-not-set`. Isso é esperado e tratado — o app loga
`MessagingService.syncToken skipped: ...` e segue normalmente. Para testar push
de verdade, use um **dispositivo físico** com uma APNs Authentication Key
configurada no Firebase (Configurações do projeto → Cloud Messaging).

## Segurança

- API keys de cliente Firebase identificam o projeto e vão embutidas no app; a
  proteção real vem das **Regras de Segurança / App Check**, não do segredo da
  key. Ainda assim, este repo opta por **não versioná-las**.
- Restrinja cada API key no Google Cloud Console (por app/bundle id).
- Se uma key vazar no histórico do git, **rotacione-a** no console e considere
  reescrever o histórico. (A key Android já esteve versionada — veja o README.)
