import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { forkJoin } from 'rxjs';

import { DashboardResponse } from '../../core/models/dashboard.model';
import { CarrierService } from '../../core/services/carrier.service';
import { DashboardService } from '../../core/services/dashboard.service';
import { PartnerService } from '../../core/services/partner.service';

// Rótulos de `StatusPedido` (commerce-service/app/services/status_pedido.py)
// e do sentinela `SEM_CHAVE_STATUS` do analytics-service — tradução na
// exibição, o serviço fala o idioma do backend.
const STATUS_LABELS: Record<string, string> = {
  CRIADO: 'Criado',
  CONFIRMADO: 'Confirmado',
  AGUARDANDO_SEPARACAO: 'Aguardando separação',
  EM_SEPARACAO: 'Em separação',
  SEPARADO: 'Separado',
  AGUARDANDO_COLETA: 'Aguardando coleta',
  EM_TRANSITO: 'Em trânsito',
  ENTREGUE: 'Entregue',
  CANCELADO: 'Cancelado',
  sem_status: 'Sem status'
};

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  private readonly dashboardService = inject(DashboardService);
  private readonly carrierService = inject(CarrierService);
  private readonly partnerService = inject(PartnerService);
  private readonly cdr = inject(ChangeDetectorRef);

  data: DashboardResponse | null = null;
  activePartners = 0;
  activeCarriers = 0;
  loading = true;
  errorMessage = '';

  ngOnInit(): void {
    forkJoin({
      dashboard: this.dashboardService.getDashboard(30),
      partners: this.partnerService.listPartners(true, 1, 0),
      carriers: this.carrierService.listCarriers(1, 0, '', 'ACTIVE')
    }).subscribe({
      next: ({ dashboard, partners, carriers }) => {
        this.data = dashboard;
        this.activePartners = partners.total;
        this.activeCarriers = carriers.total;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.errorMessage = 'Não foi possível carregar o dashboard.';
        this.loading = false;
        this.cdr.markForCheck();
      }
    });
  }

  get statusEntries(): [string, number][] {
    return Object.entries(this.data?.metricas.pedidos_por_status ?? {});
  }

  statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? status;
  }
}
