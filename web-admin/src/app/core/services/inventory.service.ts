import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { EMPTY, expand, forkJoin, map, Observable, reduce } from 'rxjs';

import {
  InventoryItem,
  InventoryList,
  InventorySummary,
  inventoryStatus
} from '../models/inventory.model';
import { ProductService } from './product.service';

export interface InventoryPageResult {
  items: InventoryItem[];
  /** `true` quando o corte de segurança (`MAX_ITEMS`) foi atingido antes do
   *  fim real dos dados — ou seja, existem mais linhas de estoque do que as
   *  carregadas. `false` significa que a última página veio curta, o que
   *  É o fim dos dados (a rota não devolve `total` para comparar contra). */
  truncated: boolean;
}

@Injectable({ providedIn: 'root' })
export class InventoryService {
  private readonly http = inject(HttpClient);
  private readonly productService = inject(ProductService);
  private readonly apiUrl = '/api';

  /** Teto da rota (`admin.py`, `limit: int = Query(..., le=200)`) — a maior
   *  página que o backend aceita por chamada. */
  private static readonly PAGE_LIMIT = 200;
  /** Corte de segurança do cliente: acima disto, paramos de paginar mesmo
   *  que existam mais linhas, e sinalizamos `truncated`. O painel opera
   *  dezenas/centenas de linhas — 2000 é uma folga generosa, não um limite
   *  de negócio. */
  private static readonly MAX_ITEMS = 2000;

  /** `GET /admin/inventory` não tem `search` nem `lowStock` no backend, e
   *  não devolve envelope nem `total` (ver inventory.model.ts) — uma única
   *  chamada só enxerga uma página. Uso interno de `listAllInventory()`;
   *  exposto porque é o primitivo real da rota. */
  listInventory(limit = InventoryService.PAGE_LIMIT, offset = 0): Observable<InventoryList> {
    const params = new HttpParams()
      .set('limit', String(limit))
      .set('offset', String(offset));

    return this.http.get<InventoryList>(`${this.apiUrl}/admin/inventory`, {
      params
    });
  }

  /** Pagina `GET /admin/inventory` até vir uma página mais curta que
   *  `PAGE_LIMIT` (isso É o fim dos dados — a rota não devolve `total`) ou
   *  até `MAX_ITEMS`. Sem isto, qualquer tela que dependesse de uma única
   *  chamada com `limit=100` mentiria a partir da linha 101: contador
   *  errado, "estoque baixo" subcontado, busca com falso negativo em linhas
   *  fora da primeira página. Mesmo padrão que `getAllLowStockPages`
   *  (versão anterior desta tela contra a API Java) já usava. */
  listAllInventory(): Observable<InventoryPageResult> {
    const pageLimit = InventoryService.PAGE_LIMIT;
    const maxItems = InventoryService.MAX_ITEMS;

    return this.listInventory(pageLimit, 0).pipe(
      map(page => ({ page, offset: 0 })),
      expand(({ page, offset }) => {
        const nextOffset = offset + pageLimit;
        const pageWasFull = page.length === pageLimit;

        if (!pageWasFull || nextOffset >= maxItems) {
          return EMPTY;
        }

        return this.listInventory(pageLimit, nextOffset).pipe(
          map(nextPage => ({ page: nextPage, offset: nextOffset }))
        );
      }),
      reduce(
        (acc, { page, offset }) => ({
          items: [...acc.items, ...page],
          truncated:
            acc.truncated ||
            (page.length === pageLimit && offset + pageLimit >= maxItems)
        }),
        { items: [] as InventoryItem[], truncated: false as boolean }
      )
    );
  }

  /** `estoqueId` é o id da linha de ESTOQUE (`InventoryItem.id`), não o do
   *  produto. `quantidade` é o novo valor ABSOLUTO, e `motivo` é
   *  obrigatório desde a task 3 (auditoria) — os dois vão como query
   *  param, não como body. */
  adjustInventory(
    estoqueId: number,
    quantidade: number,
    motivo: string
  ): Observable<InventoryItem> {
    const params = new HttpParams()
      .set('quantidade', String(quantidade))
      .set('motivo', motivo);

    return this.http.patch<InventoryItem>(
      `${this.apiUrl}/admin/inventory/${estoqueId}/adjust`,
      null,
      { params }
    );
  }

  /** Conta sobre TODAS as linhas carregadas (`listAllInventory`), não sobre
   *  uma única página de 100 — não depende mais do dashboard, que não tem
   *  nenhum dado de estoque (task 13, passo 6).
   *
   *  `totalProducts` vem de `GET /products?limit=1` (`.total`), não de
   *  contar linhas de estoque: `Estoque` é único na PAR
   *  `(produto_id, fornecedor_id)`, então um produto vendido por dois
   *  parceiros gera duas linhas e contá-las dobraria esse produto. O
   *  catálogo (`ProductList.total`) é a contagem correta, medida pelo
   *  servidor. */
  getSummary(): Observable<InventorySummary> {
    return forkJoin({
      inventory: this.listAllInventory(),
      productCatalog: this.productService.listProducts(1, 0)
    }).pipe(
      map(({ inventory, productCatalog }) => ({
        totalProducts: productCatalog.total,
        lowStock: inventory.items.filter(
          item => inventoryStatus(item) === 'LOW_STOCK'
        ).length,
        outOfStock: inventory.items.filter(
          item => inventoryStatus(item) === 'OUT_OF_STOCK'
        ).length
      }))
    );
  }
}
