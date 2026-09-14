import 'package:edu_ia/features/logistics/presentation/shipment_login_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/add_payment_method_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/checkout_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/order_details_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/orders_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/marketplace_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/product_detail_screen.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_screen.dart';
import 'package:edu_ia/features/order_tracking/presentation/order_map_screen.dart';
import 'package:edu_ia/features/order_tracking/presentation/order_tracking_screen.dart';
import 'package:edu_ia/features/quiz/presentation/quiz_screen.dart';
import 'package:edu_ia/features/quiz/presentation/quiz_subjets_screen.dart';
import 'package:edu_ia/features/review/presentation/review_screen.dart';
import 'package:edu_ia/features/tracker/presentation/tracker_screen.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import 'core/locale/app_locale.dart';
import 'core/network/app_http.dart';
import 'core/network/token_refresher.dart';
import 'core/network/token_store.dart';
import 'core/session/session_manager.dart';
import 'core/theme/app_theme.dart';
import 'features/cart/data/cart_store.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/auth/presentation/register_screen.dart';
import 'features/auth/presentation/forgot_password_screen.dart';
import 'features/auth/presentation/reset_password_screen.dart';
import 'features/home/presentation/home_screen.dart';
import 'features/notifications/data/notifications_api.dart';
import 'features/notifications/data/outras_sessoes_guardadas.dart';
import 'features/notifications/data/plugin_local_notifier.dart';
import 'features/notifications/presentation/notifications_poller.dart';
import 'features/notifications/presentation/system_notification_tap.dart';
import 'features/onboarding/presentation/onboarding_screen.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/profile/presentation/addresses_screen.dart';
import 'features/profile/presentation/address_form_screen.dart';
import 'features/support/presentation/support_screen.dart';

// NOTA: as rotas nomeadas '/logistics', '/logistics-dashboard' e
// '/logistics-picking' (e as telas LogisticsLoginScreen,
// LogisticsDashboardScreen, OrderPickingScreen que elas apontavam) foram
// removidas. Com o RBAC unificado no Auth + Users Service, separador e
// entregador agora entram pelo MESMO '/login' e são redirecionados
// automaticamente para SeparadorFilaScreen/EntregadorFilaScreen
// (features/logistics/presentation/) com base no claim `role` do JWT — ver
// `_redirecionarPorPapel()` em login_screen.dart. Os três arquivos antigos
// podem ser deletados do projeto; ver STATUS.md.

// Sem Firebase: o envio de push morreu junto com o monolito na spec A, e o
// notification-service que sobreviveu apenas GUARDA o token do dispositivo —
// nada envia para ele (`device_token.py`). As notificações do aluno chegam por
// `GET /notifications`, lidas do Postgres pela notifications_screen. Manter a
// dependência custava a compilação num clone limpo, porque
// `firebase_options.dart` é git-ignored. A spec C reintroduz push com um
// backend capaz de enviar.
//
// Enquanto isso, o "tempo real" é LOCAL: com o app vivo, o
// `NotificationsPoller` consulta `GET /notifications` a cada 10 s e mostra na
// bandeja do sistema o que chegou (flutter_local_notifications). Não é push de
// servidor — ver docs/front-end/local_notifications.md.
void main() {
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => CartStore()),
        // Iniciado a cada login em `irParaTelaDoPapel`; lido pelo sino
        // (`NotificationBell`) e pela lista de notificações.
        ChangeNotifierProvider(create: (_) => _criarNotificationsPoller()),
      ],
      child: MaterialApp(
        title: 'Edu IA',
        navigatorKey: rootNavigatorKey,
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        locale: AppLocale.locale,
        supportedLocales: AppLocale.supportedLocales,
        localizationsDelegates: AppLocale.localizationsDelegates,
        initialRoute: '/login',
        routes: {
          '/login': (_) => const LoginScreen(),
          '/register': (_) => const RegisterScreen(),
          '/forgot-password': (_) => ForgotPasswordScreen(),
          '/reset-password': (_) => ResetPasswordScreen(),
          '/shipment-login': (_) => const ShipmentLoginScreen(),
          '/home': (_) => const HomeScreen(),
          '/profile': (_) => const ProfileScreen(),
          '/addresses': (_) => const AddressesScreen(),
          '/address-form': (_) => const AddressFormScreen(),
          '/quiz': (_) => const QuizSubjetsScreen(),
          '/review': (_) => const ReviewScreen(),
          '/questions': (_) => const QuizScreen(),
          '/notifications': (_) => const NotificationsScreen(),
          '/marketplace': (_) => const MarketplaceScreen(),
          '/product': (_) => const ProductDetailScreen(),
          '/checkout': (_) => const CheckoutScreen(),
          '/add-payment-method': (_) => const AddPaymentMethodScreen(),
          '/orders': (_) => const OrdersScreen(),
          '/support': (_) => const SupportScreen(),
          '/order-details': (_) => const OrderDetailsScreen(),
          '/order-tracking': (_) => const OrderTrackingScreen(),
          '/order-map': (_) => const OrderMapScreen(),
          '/onboarding': (_) => const OnboardingScreen(),
          '/tracker': (_) => const TrackerScreen(),
        },
      ),
    );
  }
}

/// Monta o poller do app: busca pela API real, sessão lida do [TokenStore],
/// e o toque numa notificação da bandeja navegando pelo [rootNavigatorKey].
/// Na demonstração multi-sessão, também as outras sessões guardadas.
NotificationsPoller _criarNotificationsPoller() {
  late final NotificationsPoller poller;
  poller = NotificationsPoller(
    notifier: criarLocalNotifier(
      aoTocar: (payload) => abrirNotificacaoDoSistema(
        navigator: rootNavigatorKey.currentState,
        sessaoAtiva: poller.ativo,
        payload: payload,
      ),
    ),
    buscar: NotificationsApi().list,
    lerAccessToken: TokenStore().readAccessToken,
    // Constante de compilação: no build normal nada disto é montado.
    buscarOutrasSessoes: SessionManager.habilitado
        ? _criarOutrasSessoes().buscar
        : null,
  );
  return poller;
}

/// Demonstração multi-sessão: as sessões guardadas que não são a ativa,
/// consultadas com o próprio par de tokens por um cliente HTTP simples. O
/// `appAuthClient` não serve aqui: ele troca o `Authorization` pelo token da
/// sessão ATIVA e, num 401, renova — ou desloga — a sessão ativa.
OutrasSessoesGuardadas _criarOutrasSessoes() {
  final cliente = http.Client();
  return OutrasSessoesGuardadas(
    sessoes: SessionManager(),
    buscarComToken: NotificationsApi(client: cliente).listWithToken,
    renovar: TokenRefresher(client: cliente).exchange,
  );
}
