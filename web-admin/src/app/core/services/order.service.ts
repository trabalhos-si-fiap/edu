import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { OrderStatus, StaffOrder } from '../models/order.model';

@Injectable({ providedIn: 'root' })
export class OrderService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  /** `GET /admin/orders` devolve um array puro, sem envelope nem `total`
   *  (mesmo formato de `/admin/inventory`) — quem pagina só sabe que pode
   *  haver próxima página quando a atual volta cheia. Mais novo primeiro.
   *  `limit` tem teto de 200 no backend. */
  listOrders(
    limit = 10,
    offset = 0,
    status: OrderStatus | '' = ''
  ): Observable<StaffOrder[]> {
    let params = new HttpParams()
      .set('limit', String(limit))
      .set('offset', String(offset));

    if (status) {
      params = params.set('status', status);
    }

    return this.http.get<StaffOrder[]>(`${this.apiUrl}/admin/orders`, {
      params
    });
  }

  /** CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO numa chamada só (ver o
   *  docstring de `confirmar_pagamento` em admin.py). Devolve o pedido já
   *  no estado final — a tela troca a linha por ele, sem recarregar. */
  confirmPayment(orderId: string): Observable<StaffOrder> {
    return this.http.patch<StaffOrder>(
      `${this.apiUrl}/admin/orders/${orderId}/confirm-payment`,
      null
    );
  }
}
