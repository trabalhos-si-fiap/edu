/** A sentença de erro é do SERVIDOR; o cliente exibe, não reescreve.
 *
 * Mesma regra que o app Flutter passou a seguir na spec B (ruling 17): o
 * backend já responde `detail` em português, pensado para ser mostrado ao
 * usuário — "O ajuste deixaria o estoque negativo", "Já existe um produto com
 * este SKU". Trocar isso por uma frase genérica joga fora a única informação
 * que diz o que fazer a seguir, e no caso do ajuste de estoque chegava a
 * DESINFORMAR: 422 virava "Confira a quantidade e o motivo do ajuste" quando o
 * 422 mais provável ali é a recusa de estoque negativo.
 *
 * O `detail` do FastAPI é string quando vem de um `HTTPException`, mas é uma
 * LISTA de objetos quando vem da validação do Pydantic (422 de schema). Só a
 * string é exibível — para o resto fica o texto genérico de quem chamou.
 */
export function backendDetail(error: unknown, fallback: string): string {
  const detail = (error as { error?: { detail?: unknown } })?.error?.detail;

  return typeof detail === 'string' && detail.trim() !== ''
    ? detail
    : fallback;
}
