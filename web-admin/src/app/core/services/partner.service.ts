import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { EMPTY, expand, Observable, reduce } from 'rxjs';

import { Partner, PartnerList } from '../models/partner.model';

@Injectable({ providedIn: 'root' })
export class PartnerService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  /** Teto da rota (`parceiros.py`, `limit: int = Query(..., le=100)`) — a
   *  maior página que o backend aceita por chamada. */
  private static readonly PAGE_LIMIT = 100;

  /** Sem paginação real na tela — o painel opera dezenas de parceiros, não
   *  milhares (mesma decisão do estoque, ver inventory.service.ts). */
  listPartners(active = false, limit = 100, offset = 0): Observable<PartnerList> {
    const params = new HttpParams()
      .set('active', String(active))
      .set('limit', String(limit))
      .set('offset', String(offset));

    return this.http.get<PartnerList>(`${this.apiUrl}/partners`, { params });
  }

  /** Todos os parceiros, ativos e inativos, paginando até `total`. Existe
   *  porque `active` na rota só ESTREITA para ativos: `active=false` é
   *  "todos", não "só inativos" (`listar_parceiros`, parceiros.py) — então
   *  a tela de parceiros filtra no cliente, sobre a lista inteira, como a de
   *  produtos e estoque já faz com o que o backend não filtra. */
  listAllPartners(): Observable<Partner[]> {
    const pageLimit = PartnerService.PAGE_LIMIT;

    return this.listPartners(false, pageLimit, 0).pipe(
      expand(page => {
        const nextOffset = page.offset + pageLimit;
        const hasMore =
          page.items.length === pageLimit && nextOffset < page.total;

        return hasMore
          ? this.listPartners(false, pageLimit, nextOffset)
          : EMPTY;
      }),
      reduce((all, page) => [...all, ...page.items], [] as Partner[])
    );
  }
}
