/** Espelha `ResumoMetricasOut` (analytics-service). */
export interface DashboardMetrics {
  pedidos_criados: number;
  pedidos_por_status: Record<string, number>;
  ocorrencias_abertas: number;
  ocorrencias_resolvidas: number;
  diagnosticos_por_acao: Record<string, number>;
}

/** Espelha `ResumoExecutivoOut` — `GET /analytics/executive-summary`.
 *
 *  Não existe `/dashboard`: os campos educacionais e boa parte dos
 *  operacionais do painel antigo (alunos cadastrados/ativos, histórico de
 *  atividade, produtos cadastrados/estoque baixo, lista de transportadoras,
 *  ocorrências recentes) não têm fonte aqui — nenhum é inventado no
 *  cliente. Ver task-13-report.md / task 14 para a lista completa do que
 *  saiu de tela. */
export interface DashboardResponse {
  periodo_dias: number;
  metricas: DashboardMetrics;
  resumo_executivo: string;
}
