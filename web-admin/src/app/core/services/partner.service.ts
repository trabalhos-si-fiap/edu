import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { PartnerList } from '../models/partner.model';

@Injectable({ providedIn: 'root' })
export class PartnerService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  /** Sem paginação real na tela — o painel opera dezenas de parceiros, não
   *  milhares (mesma decisão do estoque, ver inventory.service.ts). */
  listPartners(active = false, limit = 100, offset = 0): Observable<PartnerList> {
    const params = new HttpParams()
      .set('active', String(active))
      .set('limit', String(limit))
      .set('offset', String(offset));

    return this.http.get<PartnerList>(`${this.apiUrl}/partners`, { params });
  }
}
