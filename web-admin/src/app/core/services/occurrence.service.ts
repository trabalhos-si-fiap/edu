import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

import {
  Occurrence,
  OccurrenceList,
  OccurrenceStatus,
  OccurrenceType
} from '../models/occurrence.model';
import { DashboardService } from './dashboard.service';

@Injectable({ providedIn: 'root' })
export class OccurrenceService {
  private readonly http = inject(HttpClient);
  private readonly dashboardService = inject(DashboardService);
  private readonly apiUrl = '/api';

  listOccurrences(
    limit = 3,
    offset = 0,
    carrierId: number | null = null,
    tipo: OccurrenceType | '' = '',
    status: OccurrenceStatus | '' = ''
  ): Observable<OccurrenceList> {
    let params = new HttpParams()
      .set('limit', String(limit))
      .set('offset', String(offset));

    if (carrierId !== null) {
      params = params.set('carrier_id', String(carrierId));
    }

    if (tipo) {
      params = params.set('tipo', tipo);
    }

    if (status) {
      params = params.set('status', status);
    }

    return this.http.get<OccurrenceList>(`${this.apiUrl}/occurrences`, {
      params
    });
  }

  /** Fecha a ocorrência. Não existe "reabrir" no backend — `POST
   *  /occurrences/{id}/close` só transiciona ABERTA -> RESOLVIDA, uma via
   *  — diferente do toggle bidirecional que a tela tinha contra a API
   *  Java. `invalidateCache()` porque `ocorrencias_abertas`/
   *  `ocorrencias_resolvidas` vêm do dashboard (analytics). */
  close(id: number, observacao?: string): Observable<Occurrence> {
    return this.http
      .post<Occurrence>(`${this.apiUrl}/occurrences/${id}/close`, {
        observacao: observacao ?? null
      })
      .pipe(tap(() => this.dashboardService.invalidateCache()));
  }
}
