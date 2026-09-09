export type OccurrenceType =
  | 'FALTA_ESTOQUE'
  | 'ATRASO_ENTREGA'
  | 'DANO'
  | 'FALHA_ENTREGA'
  | 'OUTRO';

export type OccurrenceStatus = 'ABERTA' | 'RESOLVIDA';

/** Espelha `OcorrenciaOut` por inteiro — inclui `produto_id`,
 *  `nova_data_sugerida` e `resolucao`, que toda ocorrência devolve (não só
 *  as de transportadora), medido em
 *  back-end/commerce-service/app/schemas/ocorrencia.py.
 *
 *  Não existe `carrier_name`: a tela resolve o nome cruzando
 *  `transportadora_id` com a lista de transportadoras já carregada — junção
 *  no cliente, mesma decisão do estoque (ver occurrences.component.ts). */
export interface Occurrence {
  id: number;
  pedido_id: string;
  tipo: OccurrenceType;
  status: OccurrenceStatus;
  produto_id: string | null;
  transportadora_id: number | null;
  nova_data_sugerida: string | null;
  motivo: string;
  resolucao: string | null;
  criado_em: string;
  resolvido_em: string | null;
}

export interface OccurrenceList {
  items: Occurrence[];
  total: number;
  limit: number;
  offset: number;
}
