import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { map, Observable } from 'rxjs';

import {
  InventoryItem,
  InventoryList,
  InventorySummary,
  inventoryStatus
} from '../models/inventory.model';

@Injectable({ providedIn: 'root' })
export class InventoryService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  /** `GET /admin/inventory` não tem `search` nem `lowStock` no backend, e
   *  não devolve envelope (ver inventory.model.ts). A spec escolheu filtrar
   *  no cliente sobre `limit=100` — o painel opera dezenas de linhas, não
   *  milhares. */
  listInventory(limit = 100, offset = 0): Observable<InventoryList> {
    const params = new HttpParams()
      .set('limit', String(limit))
      .set('offset', String(offset));

    return this.http.get<InventoryList>(`${this.apiUrl}/admin/inventory`, {
      params
    });
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

  /** Conta sobre a página carregada — não depende mais do dashboard, que
   *  não tem nenhum dado de estoque (task 13, passo 6). */
  getSummary(): Observable<InventorySummary> {
    return this.listInventory(100, 0).pipe(
      map(items => ({
        totalProducts: items.length,
        lowStock: items.filter(
          item => inventoryStatus(item) === 'LOW_STOCK'
        ).length,
        outOfStock: items.filter(
          item => inventoryStatus(item) === 'OUT_OF_STOCK'
        ).length
      }))
    );
  }
}
