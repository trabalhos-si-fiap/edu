/** Espelha `ParceiroOut` (commerce-service). Não estava no escopo original
 *  do painel — a task 13 precisa dele para o seletor de fornecedor no
 *  formulário de produto (`POST /products` exige `fornecedor_id`) e para o
 *  total de parceiros ativos do dashboard.
 *
 *  Campos em português — o serviço fala o idioma do backend; a tradução
 *  acontece na exibição. `origem_lat`/`origem_lng` chegam como STRING pelo
 *  mesmo motivo de `Product.price`. */
export interface Partner {
  id: number;
  nome: string;
  contato: string | null;
  ativo: boolean;
  origem_rotulo: string;
  origem_lat: string | null;
  origem_lng: string | null;
}

export interface PartnerList {
  items: Partner[];
  total: number;
  limit: number;
  offset: number;
}
