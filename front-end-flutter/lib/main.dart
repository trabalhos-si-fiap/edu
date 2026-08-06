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
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/network/app_http.dart';
import 'core/theme/app_theme.dart';
import 'features/cart/data/cart_store.dart';
import 'features/notifications/data/messaging_service.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/auth/presentation/register_screen.dart';
import 'features/auth/presentation/forgot_password_screen.dart';
import 'features/auth/presentation/reset_password_screen.dart';
import 'features/home/presentation/home_screen.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/profile/presentation/addresses_screen.dart';
import 'features/profile/presentation/address_form_screen.dart';
import 'features/support/presentation/support_screen.dart';
import 'firebase_options.dart';

// NOTA: as rotas nomeadas '/logistics', '/logistics-dashboard' e
// '/logistics-picking' (e as telas LogisticsLoginScreen,
// LogisticsDashboardScreen, OrderPickingScreen que elas apontavam) foram
// removidas. Com o RBAC unificado no Auth + Users Service, separador e
// entregador agora entram pelo MESMO '/login' e são redirecionados
// automaticamente para SeparadorFilaScreen/EntregadorFilaScreen
// (features/logistics/presentation/) com base no claim `role` do JWT — ver
// `_redirecionarPorPapel()` em login_screen.dart. Os três arquivos antigos
// podem ser deletados do projeto; ver STATUS.md.

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  @override
  void initState() {
    super.initState();
    // Permission + foreground display + token-refresh wiring, set up once.
    MessagingService().init();
  }

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
          '/home': (_) => const HomeScreen(),
          '/profile': (_) => const ProfileScreen(),
          '/addresses': (_) => const AddressesScreen(),
          '/address-form': (_) => const AddressFormScreen(),
          '/quiz': (_) => const QuizSubjetsScreen(),
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
        },
      ),
    );
  }
}
