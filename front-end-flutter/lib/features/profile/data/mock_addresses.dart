import '../domain/address.dart';

/// Endereços mockados do usuário. Substitui o AddressRepository (API) do edu-kt.
const List<Address> mockAddresses = [
  Address(
    id: '1',
    label: 'Casa',
    zipCode: '01310-100',
    street: 'Av. Paulista',
    number: '1000',
    complement: 'Apto 52',
    neighborhood: 'Bela Vista',
    city: 'São Paulo',
    state: 'SP',
    isFavorite: true,
  ),
  Address(
    id: '2',
    label: 'Trabalho',
    zipCode: '04538-133',
    street: 'Av. Brigadeiro Faria Lima',
    number: '3477',
    complement: '12º andar',
    neighborhood: 'Itaim Bibi',
    city: 'São Paulo',
    state: 'SP',
    isFavorite: false,
  ),
];
