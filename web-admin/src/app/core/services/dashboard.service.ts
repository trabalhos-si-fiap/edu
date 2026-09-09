import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, shareReplay } from 'rxjs';

import { DashboardResponse } from '../models/dashboard.model';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  private dashboard30Days$?: Observable<DashboardResponse>;

  getDashboard(dias = 30): Observable<DashboardResponse> {
    if (dias === 30) {
      if (!this.dashboard30Days$) {
        this.dashboard30Days$ = this.requestDashboard(dias).pipe(
          shareReplay({ bufferSize: 1, refCount: false })
        );
      }

      return this.dashboard30Days$;
    }

    return this.requestDashboard(dias);
  }

  invalidateCache(): void {
    this.dashboard30Days$ = undefined;
  }

  private requestDashboard(dias: number): Observable<DashboardResponse> {
    const params = new HttpParams().set('dias', String(dias));

    return this.http.get<DashboardResponse>(
      `${this.apiUrl}/analytics/executive-summary`,
      { params }
    );
  }
}
