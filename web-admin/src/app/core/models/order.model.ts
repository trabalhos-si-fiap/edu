/** O pedido da visão de staff (`PedidoStaffOut`) já está espelhado em
 *  `StaffOrder` (shipment.model.ts) — a tela de carregamentos o usou
 *  primeiro. Este arquivo só acrescenta o vocabulário de status. */
export type { StaffOrder } from './shipment.model';

/** Os dez valores de `StatusPedido`
 *  (commerce-service/app/services/status_pedido.py), na ordem do fluxo.
 *  `GET /admin/orders` expõe o estado INTERNO, não os seis do contrato do
 *  aluno, e filtra por igualdade exata: um `status` que não existe não dá
 *  422, dá lista vazia — por isso o filtro só oferece estes. */
export type OrderStatus =
  | 'CRIADO'
  | 'CONFIRMADO'
  | 'AGUARDANDO_SEPARACAO'
  | 'EM_SEPARACAO'
  | 'AGUARDANDO_SUBSTITUICAO'
  | 'SEPARADO'
  | 'AGUARDANDO_COLETA'
  | 'EM_TRANSITO'
  | 'ENTREGUE'
  | 'CANCELADO';

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  CRIADO: 'Criado',
  CONFIRMADO: 'Confirmado',
  AGUARDANDO_SEPARACAO: 'Aguardando separação',
  EM_SEPARACAO: 'Em separação',
  AGUARDANDO_SUBSTITUICAO: 'Aguardando substituição',
  SEPARADO: 'Separado',
  AGUARDANDO_COLETA: 'Aguardando coleta',
  EM_TRANSITO: 'Em trânsito',
  ENTREGUE: 'Entregue',
  CANCELADO: 'Cancelado'
};
