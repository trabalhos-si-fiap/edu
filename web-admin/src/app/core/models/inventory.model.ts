export type InventoryStatus = 'NORMAL' | 'LOW_STOCK' | 'OUT_OF_STOCK';

/** Espelha `EstoqueOut`. `id` é o do ESTOQUE — é ele que a rota de ajuste
 *  (`PATCH /admin/inventory/{id}/adjust`) endereça, não o do produto
 *  (`produto_id`). */
export interface InventoryItem {
  id: number;
  produto_id: string;
  fornecedor_id: number;
  quantidade: number;
  estoque_minimo: number;
  atualizado_em: string | null;
}

/** `GET /admin/inventory` devolve um array puro
 *  (`response_model=list[EstoqueOut]`, ver
 *  back-end/commerce-service/app/routers/admin.py) — não o envelope
 *  `{items,total,limit,offset}` que os outros endpoints de listagem usam.
 *  Divergência da medição original da task; ver task-13-report.md. */
export type InventoryList = InventoryItem[];

/** Derivado no cliente a partir de `quantidade` e `estoque_minimo` — o
 *  backend não devolve rótulo de status. Isto é CÁLCULO, não invenção: as
 *  duas parcelas vêm do servidor. */
export function inventoryStatus(item: InventoryItem): InventoryStatus {
  if (item.quantidade <= 0) return 'OUT_OF_STOCK';
  if (item.quantidade <= item.estoque_minimo) return 'LOW_STOCK';
  return 'NORMAL';
}

/** Linha de exibição: junta `InventoryItem` com o nome/SKU do produto, que
 *  `EstoqueOut` não traz. Junção no CLIENTE por falta de rota agregada —
 *  ver products-stock.component.ts. Pendência registrada na task 14. */
export interface InventoryStockRow extends InventoryItem {
  productName: string;
  sku: string;
  status: InventoryStatus;
}

export interface InventorySummary {
  totalProducts: number;
  lowStock: number;
  outOfStock: number;
}
