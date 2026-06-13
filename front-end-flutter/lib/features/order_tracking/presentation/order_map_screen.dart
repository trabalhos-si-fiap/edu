import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/order_route.dart';
import 'route_provider.dart';
import 'widgets/marker_icons.dart';
import 'widgets/order_error_view.dart';
import 'widgets/order_format.dart';

/// Tela do mapa: rota real entre o Centro de Distribuição e o destino.
///
/// Recebe o id do pedido via `Navigator.pushNamed(arguments: '<id>')`,
/// delega o estado ao [RouteProvider] e renderiza o [GoogleMap] no sucesso.
class OrderMapScreen extends StatelessWidget {
  const OrderMapScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final orderId =
        ModalRoute.of(context)?.settings.arguments as String? ?? 'ED-99420';

    return ChangeNotifierProvider(
      create: (_) => RouteProvider()..load(orderId),
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          title: const Text(
            'Rota da Entrega',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 18),
          ),
          leading: IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          ),
        ),
        body: Consumer<RouteProvider>(
          builder: (context, provider, _) {
            switch (provider.state) {
              case RouteViewState.loading:
                return const Center(
                  child: CircularProgressIndicator(color: AppColors.purple),
                );
              case RouteViewState.error:
                return OrderErrorView(
                  message: provider.errorMessage ?? 'Erro desconhecido.',
                  onRetry: provider.retry,
                );
              case RouteViewState.success:
                return _RouteMap(route: provider.route!);
            }
          },
        ),
      ),
    );
  }
}

class _RouteMap extends StatefulWidget {
  final OrderRoute route;

  const _RouteMap({required this.route});

  @override
  State<_RouteMap> createState() => _RouteMapState();
}

class _RouteMapState extends State<_RouteMap> {
  /// Ícone de caminhão para o ponto de partida; nulo até a imagem ser gerada
  /// (o marcador usa o pino padrão nesse meio tempo).
  BitmapDescriptor? _truckIcon;

  @override
  void initState() {
    super.initState();
    truckMarkerBitmap().then((icon) {
      if (mounted) setState(() => _truckIcon = icon);
    });
  }

  @override
  Widget build(BuildContext context) {
    final route = widget.route;
    final origin = route.origin.latLng;
    final destination = route.destination.latLng;

    return Stack(
      children: [
        GoogleMap(
          initialCameraPosition: CameraPosition(target: origin, zoom: 10),
          onMapCreated: (controller) {
            // Defer to the next frame: at onMapCreated time the map can still
            // have zero size on Android, which makes newLatLngBounds throw and
            // leaves the camera on the origin-only initial position.
            WidgetsBinding.instance.addPostFrameCallback((_) {
              controller.animateCamera(
                CameraUpdate.newLatLngBounds(_bounds(origin, destination), 64),
              );
            });
          },
          markers: {
            Marker(
              markerId: const MarkerId('origin'),
              position: origin,
              icon: _truckIcon ?? BitmapDescriptor.defaultMarker,
              infoWindow: InfoWindow(title: route.origin.label),
            ),
            Marker(
              markerId: const MarkerId('destination'),
              position: destination,
              infoWindow: InfoWindow(title: route.destination.label),
            ),
          },
          polylines: {
            Polyline(
              polylineId: const PolylineId('route'),
              color: AppColors.purple,
              width: 5,
              points: route.polylinePoints,
            ),
          },
        ),
        Positioned(
          left: 16,
          right: 16,
          bottom: 16,
          child: _RouteSummaryCard(route: route),
        ),
      ],
    );
  }

  LatLngBounds _bounds(LatLng a, LatLng b) {
    return LatLngBounds(
      southwest: LatLng(math.min(a.latitude, b.latitude), math.min(a.longitude, b.longitude)),
      northeast: LatLng(math.max(a.latitude, b.latitude), math.max(a.longitude, b.longitude)),
    );
  }
}

/// Cartão flutuante com o resumo da rota: distância, tempo de trajeto e a
/// chegada estimada (agora + duração da rota).
class _RouteSummaryCard extends StatelessWidget {
  final OrderRoute route;

  const _RouteSummaryCard({required this.route});

  @override
  Widget build(BuildContext context) {
    final arrival = OrderFormat.estimatedArrivalLabel(
      route.estimatedArrival(DateTime.now()),
    );
    final trip = [
      route.distanceText,
      if (route.durationText.isNotEmpty) '${route.durationText} de trajeto',
    ].where((s) => s.trim().isNotEmpty).join(' • ');

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.12),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _point(Icons.local_shipping, AppColors.purple, 'Saída', route.origin.label),
          const SizedBox(height: 8),
          _point(Icons.place, AppColors.purple, 'Destino', route.destination.label),
          const Divider(height: 24),
          if (trip.isNotEmpty)
            Text(
              trip,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
                fontWeight: FontWeight.w600,
              ),
            ),
          const SizedBox(height: 4),
          Row(
            children: [
              const Text(
                'Chegada estimada: ',
                style: TextStyle(fontSize: 15, color: AppColors.textSecondary),
              ),
              Expanded(
                child: Text(
                  arrival,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _point(IconData icon, Color color, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: color),
        const SizedBox(width: 10),
        Text(
          '$label: ',
          style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
        ),
      ],
    );
  }
}
