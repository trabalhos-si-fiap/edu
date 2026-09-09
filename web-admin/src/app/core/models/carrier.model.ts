export type CarrierStatus = 'ACTIVE' | 'INACTIVE';

/** Espelha `TransportadoraIn` — payload de criação/edição. */
export interface CarrierRequest {
  name: string;
  location: string;
  email: string;
  average_delivery_days: number;
  rating: number;
  sla_percentage: number;
  status: CarrierStatus;
}

/** Espelha `TransportadoraOut`. `rating`/`sla_percentage` chegam como
 *  STRING — o backend serializa nota e SLA como texto para o cliente não
 *  herdar erro de arredondamento de float (mesmo critério de
 *  `Product.price`). `average_delivery_days` é snake_case. */
export interface Carrier {
  id: number;
  name: string;
  location: string;
  email: string;
  average_delivery_days: number;
  rating: string;
  sla_percentage: string;
  status: CarrierStatus;
  created_at: string;
  updated_at: string;
}

export interface CarrierList {
  items: Carrier[];
  total: number;
  limit: number;
  offset: number;
}

export interface CarrierSummary {
  total: number;
  active: number;
  inactive: number;
}
