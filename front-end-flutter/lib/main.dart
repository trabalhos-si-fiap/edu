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
import 'package:provider/provider.dart';
import 'core/network/app_http.dart';
import 'core/theme/app_theme.dart';
import 'features/cart/data/cart_store.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/auth/presentation/register_screen.dart';
import 'features/auth/presentation/forgot_password_screen.dart';
import 'features/auth/presentation/reset_password_screen.dart';
import 'features/home/presentation/home_screen.dart';
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
      ],
      child: MaterialApp(
        title: 'Edu IA',
        navigatorKey: rootNavigatorKey,
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
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
