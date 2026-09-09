import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  Shipment,
  ShipmentCreated,
  ShipmentList,
  StaffOrder
} from '../models/shipment.model';

@Injectable({ providedIn: 'root' })
export class ShipmentService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  listShipments(limit = 10, offset = 0): Observable<ShipmentList> {
    const params = new HttpParams()
      .set('limit', String(limit))
      .set('offset', String(offset));

    return this.http.get<ShipmentList>(`${this.apiUrl}/shipments`, {
      params
    });
  }

  /** Único ponto de contato com `senha` no cliente: a resposta chega,
   *  a página exibe uma vez e descarta — nada aqui a retém. */
  createShipment(carrierId: number): Observable<ShipmentCreated> {
    return this.http.post<ShipmentCreated>(`${this.apiUrl}/shipments`, {
      transportadora_id: carrierId
    });
  }

  assignOrder(shipmentId: number, orderId: string): Observable<void> {
    return this.http.post<void>(
      `${this.apiUrl}/shipments/${shipmentId}/orders`,
      { pedido_id: orderId }
    );
  }

  /** Sem paginação exposta na tela — um carregamento carrega dezenas de
   *  pedidos, não milhares (mesma decisão do estoque/parceiros). `limit`
   *  fixo abaixo do teto do backend (200, ver contrato da task). */
  listOrders(shipmentId: number): Observable<StaffOrder[]> {
    const params = new HttpParams().set('limit', '200').set('offset', '0');

    return this.http.get<StaffOrder[]>(
      `${this.apiUrl}/shipments/${shipmentId}/orders`,
      { params }
    );
  }
}
