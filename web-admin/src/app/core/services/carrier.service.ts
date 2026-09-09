import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { forkJoin, map, Observable } from 'rxjs';

import {
  Carrier,
  CarrierList,
  CarrierRequest,
  CarrierStatus,
  CarrierSummary
} from '../models/carrier.model';

@Injectable({ providedIn: 'root' })
export class CarrierService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  listCarriers(
    limit = 3,
    offset = 0,
    search = '',
    status: CarrierStatus | '' = ''
  ): Observable<CarrierList> {
    let params = new HttpParams()
      .set('limit', String(limit))
      .set('offset', String(offset));

    const term = search.trim();
    if (term) {
      // `%`/`_` atravessam para o ILIKE do backend como wildcard literal
      // (medido em app/services/transportadoras.py, sem ESCAPE explícito —
      // o padrão do Postgres é a contrabarra). Escapamos aqui para uma
      // busca por "50%" não virar "combina com tudo que contém '50'".
      params = params.set('search', term.replace(/[%_]/g, '\\$&'));
    }

    if (status) {
      params = params.set('status', status);
    }

    return this.http.get<CarrierList>(`${this.apiUrl}/carriers`, { params });
  }

  createCarrier(request: CarrierRequest): Observable<Carrier> {
    return this.http.post<Carrier>(`${this.apiUrl}/carriers`, request);
  }

  updateCarrier(id: number, request: CarrierRequest): Observable<Carrier> {
    return this.http.put<Carrier>(`${this.apiUrl}/carriers/${id}`, request);
  }

  updateStatus(id: number, status: CarrierStatus): Observable<Carrier> {
    return this.http.patch<Carrier>(
      `${this.apiUrl}/carriers/${id}/status`,
      { status }
    );
  }

  getAllCarriers(): Observable<Carrier[]> {
    return this.listCarriers(100, 0).pipe(map(page => page.items));
  }

  /** Conta sobre `total` e sobre uma consulta com `status=ACTIVE` — não
   *  toca mais no dashboard (task 13, passo 5). */
  getSummary(): Observable<CarrierSummary> {
    return forkJoin({
      allPage: this.listCarriers(1, 0),
      activePage: this.listCarriers(1, 0, '', 'ACTIVE')
    }).pipe(
      map(({ allPage, activePage }) => {
        const total = allPage.total;
        const active = activePage.total;
        return { total, active, inactive: Math.max(0, total - active) };
      })
    );
  }
}
