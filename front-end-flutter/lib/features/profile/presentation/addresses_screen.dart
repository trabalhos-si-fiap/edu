import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/addresses_api.dart';
import '../domain/address.dart';

/// Lista e gerencia os endereços do usuário (CRUD contra `/auth/addresses`).
/// Acessada a partir de "Meu perfil".
class AddressesScreen extends StatefulWidget {
  const AddressesScreen({super.key});

  @override
  State<AddressesScreen> createState() => _AddressesScreenState();
}

class _AddressesScreenState extends State<AddressesScreen> {
  final _api = AddressesApi();

  bool _loading = true;
  String? _error;
  List<Address> _addresses = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final addresses = await _api.list();
      if (!mounted) return;
      setState(() {
        _addresses = addresses;
        _loading = false;
      });
    } on AddressException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  Future<void> _openForm({Address? address}) async {
    final saved = await Navigator.pushNamed(
      context,
      '/address-form',
      arguments: address,
    );
    if (saved == true) _load();
  }

  Future<void> _setFavorite(Address address) async {
    if (address.isFavorite) return;
    try {
      await _api.setFavorite(address.id);
      await _load();
    } on AddressException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _confirmDelete(Address address) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remover endereço'),
        content: Text(
          'Tem certeza que deseja remover '
          '"${address.label.isEmpty ? address.summary : address.label}"?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: AppColors.danger),
            child: const Text('Remover'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _api.delete(address.id);
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Endereço removido')));
      await _load();
    } on AddressException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
            onPressed: () => Navigator.pop(context),
          ),
          title: const Text(
            'Meus endereços',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 18,
            ),
          ),
        ),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: () => _openForm(),
          backgroundColor: AppColors.purple,
          foregroundColor: AppColors.white,
          icon: const Icon(Icons.add),
          label: const Text('Adicionar'),
        ),
        body: SafeArea(child: _body()),
      ),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(color: AppColors.purple),
      );
    }
    if (_error != null) {
      return _ErrorState(message: _error!, onRetry: _load);
    }
    if (_addresses.isEmpty) {
      return const _EmptyState();
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 96),
        itemCount: _addresses.length,
        separatorBuilder: (_, _) => const SizedBox(height: 12),
        itemBuilder: (_, i) {
          final address = _addresses[i];
          return _AddressCard(
            address: address,
            onEdit: () => _openForm(address: address),
            onDelete: () => _confirmDelete(address),
            onSetFavorite: () => _setFavorite(address),
          );
        },
      ),
    );
  }
}

class _AddressCard extends StatelessWidget {
  const _AddressCard({
    required this.address,
    required this.onEdit,
    required this.onDelete,
    required this.onSetFavorite,
  });

  final Address address;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onSetFavorite;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.purpleSoft,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.location_on_outlined,
                color: AppColors.purple, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        address.label.isEmpty ? 'Endereço' : address.label,
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                    if (address.isFavorite) ...[
                      const SizedBox(width: 8),
                      const _FavoriteBadge(),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  address.summary,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                    height: 1.3,
                  ),
                ),
                Text(
                  'CEP ${address.zipCode}',
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          _Menu(
            isFavorite: address.isFavorite,
            onEdit: onEdit,
            onDelete: onDelete,
            onSetFavorite: onSetFavorite,
          ),
        ],
      ),
    );
  }
}

class _Menu extends StatelessWidget {
  const _Menu({
    required this.isFavorite,
    required this.onEdit,
    required this.onDelete,
    required this.onSetFavorite,
  });

  final bool isFavorite;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onSetFavorite;

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      icon: const Icon(Icons.more_vert, color: AppColors.textSecondary),
      onSelected: (value) {
        switch (value) {
          case 'edit':
            onEdit();
          case 'favorite':
            onSetFavorite();
          case 'delete':
            onDelete();
        }
      },
      itemBuilder: (_) => [
        const PopupMenuItem(
          value: 'edit',
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.edit_outlined, color: AppColors.textPrimary),
            title: Text('Editar'),
          ),
        ),
        if (!isFavorite)
          const PopupMenuItem(
            value: 'favorite',
            child: ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.star_outline, color: AppColors.star),
              title: Text('Tornar favorito'),
            ),
          ),
        const PopupMenuItem(
          value: 'delete',
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.delete_outline, color: AppColors.danger),
            title: Text('Remover', style: TextStyle(color: AppColors.danger)),
          ),
        ),
      ],
    );
  }
}

class _FavoriteBadge extends StatelessWidget {
  const _FavoriteBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.purpleSoft,
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.star, size: 12, color: AppColors.purple),
          SizedBox(width: 4),
          Text(
            'FAVORITO',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w800,
              color: AppColors.purple,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: const BoxDecoration(
                color: AppColors.white,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.location_off_outlined,
                  size: 36, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 16),
            const Text(
              'Nenhum endereço cadastrado',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Toque em "Adicionar" para cadastrar seu primeiro endereço.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 40, color: AppColors.textSecondary),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 14, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 16),
            OutlinedButton(
              onPressed: onRetry,
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.purple,
                side: const BorderSide(color: AppColors.purple),
              ),
              child: const Text('Tentar novamente'),
            ),
          ],
        ),
      ),
    );
  }
}
