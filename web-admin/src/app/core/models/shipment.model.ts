/** Espelha `CarregamentoOut` (commerce-service, task 4 desta spec).
 *  `origem_lat`/`origem_lng` chegam como STRING — mesmo critério de
 *  `Partner.origem_lat/lng` e `Product.price` (o backend serializa para o
 *  cliente não herdar erro de arredondamento de float). */
export interface Shipment {
  id: number;
  transportadora_id: number;
  codigo: string;
  origem_rotulo: string;
  origem_lat: string | null;
  origem_lng: string | null;
  entregador_nome: string | null;
  entregador_contato: string | null;
  aberto_em: string | null;
  criado_em: string;
}

/** Resposta de `POST /shipments` — o único lugar onde `senha` aparece.
 *  Nenhuma listagem ou rota de detalhe a repete, e ela não é recuperável
 *  depois: a página que consome isto mostra e descarta, sem guardar em
 *  nenhum estado que sobreviva ao modal de credencial. */
export interface ShipmentCreated extends Shipment {
  senha: string;
}

export interface ShipmentList {
  items: Shipment[];
  total: number;
  limit: number;
  offset: number;
}

/** Espelha o item "staff view" de `GET /shipments/{id}/orders`. `total`
 *  chega como STRING pelo mesmo motivo de `Product.price`; `id`, `user_id`,
 *  `picker_id` e `deliverer_id` são UUID (texto). */
export interface StaffOrder {
  id: string;
  user_id: string;
  status: string;
  total: string;
  endereco_entrega: string;
  carrier_name: string | null;
  estimated_delivery_at: string | null;
  created_at: string;
  picker_id: string | null;
  deliverer_id: string | null;
}
