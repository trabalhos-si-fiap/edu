import 'package:edu_ia/features/marketplace/presentation/add_payment_method_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/checkout_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/order_details_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/orders_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/marketplace_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/product_detail_screen.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_screen.dart';
import 'package:edu_ia/features/order_tracking/presentation/order_tracking_screen.dart';
import 'package:edu_ia/features/quiz/presentation/quiz_screen.dart';
import 'package:edu_ia/features/quiz/presentation/quiz_subjets_screen.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/theme/app_theme.dart';
import 'features/cart/data/cart_store.dart';
import 'features/payment/data/payment_store.dart';
import 'features/notifications/data/messaging_service.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/auth/presentation/logistics_login_screen.dart';
import 'features/logistics/presentation/logistics_dashboard_screen.dart';
import 'features/logistics/presentation/order_picking_screen.dart';
import 'features/auth/presentation/register_screen.dart';
import 'features/home/presentation/home_screen.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/profile/presentation/addresses_screen.dart';
import 'features/profile/presentation/address_form_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Android reads options from google-services.json at build time, so no
  // explicit FirebaseOptions are needed here.
  await Firebase.initializeApp();
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
        ChangeNotifierProvider(create: (_) => PaymentStore()),
      ],
      child: MaterialApp(
        title: 'Edu IA',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        initialRoute: '/login',
        routes: {
          '/login': (_) => const LoginScreen(),
          '/logistics': (_) => const LogisticsLoginScreen(),
          '/logistics-dashboard': (_) => const LogisticsDashboardScreen(),
          '/logistics-picking': (_) => const OrderPickingScreen(),
          '/register': (_) => const RegisterScreen(),
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
          '/order-details': (_) => const OrderDetailsScreen(),
          '/order-tracking': (_) => const OrderTrackingScreen(),
        },
      ),
    );
  }
}
