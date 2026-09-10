import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import {
  FormBuilder,
  ReactiveFormsModule,
  Validators
} from '@angular/forms';

import { backendDetail } from '../../core/http-error';
import { Carrier } from '../../core/models/carrier.model';
import {
  Shipment,
  ShipmentCreated,
  ShipmentList,
  StaffOrder
} from '../../core/models/shipment.model';
import { CarrierService } from '../../core/services/carrier.service';
import { ShipmentService } from '../../core/services/shipment.service';
import { SuccessToastComponent } from '../../shared/success-toast/success-toast.component';

@Component({
  selector: 'app-shipments',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, SuccessToastComponent],
  templateUrl: './shipments.component.html',
  styleUrl: './shipments.component.scss'
})
export class ShipmentsComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly shipmentService = inject(ShipmentService);
  private readonly carrierService = inject(CarrierService);
  private readonly cdr = inject(ChangeDetectorRef);

  pageData: ShipmentList | null = null;
  carriers: Carrier[] = [];

  page = 0;
  readonly pageSize = 10;

  loading = true;

  // --- criação de carregamento -------------------------------------------
  showCreateModal = false;
  creating = false;
  createError = '';
  // Só existe enquanto o modal de credencial está aberto — fechar o modal
  // (closeCreateModal) descarta este valor. Nunca é lido por mais nada, não
  // vai para localStorage, e não é logado em nenhum ponto do fluxo.
  createdShipment: ShipmentCreated | null = null;

  readonly createForm = this.fb.nonNullable.group({
    carrierId: this.fb.control<number | null>(null, Validators.required)
  });

  // --- atribuição de pedido ------------------------------------------------
  assigningShipment: Shipment | null = null;
  assigning = false;
  assignError = '';
  loadingOrders = false;
  shipmentOrders: StaffOrder[] = [];

  readonly assignForm = this.fb.nonNullable.group({
    orderId: ['', [Validators.required, Validators.maxLength(64)]]
  });

  successMessage = '';
  private successTimer: number | null = null;

  ngOnInit(): void {
    this.carrierService.getAllCarriers().subscribe(carriers => {
      this.carriers = carriers;
      this.cdr.markForCheck();
    });

    this.loadPage();
  }

  loadPage(): void {
    this.loading = true;

    this.shipmentService
      .listShipments(this.pageSize, this.page * this.pageSize)
      .subscribe({
        next: data => {
          this.pageData = data;
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.loading = false;
          this.cdr.markForCheck();
        }
      });
  }

  previous(): void {
    if (this.page <= 0) return;
    this.page--;
    this.loadPage();
  }

  next(): void {
    if (!this.hasNext) return;
    this.page++;
    this.loadPage();
  }

  get hasNext(): boolean {
    return (this.page + 1) * this.pageSize < (this.pageData?.total ?? 0);
  }

  get startResult(): number {
    const total = this.pageData?.total ?? 0;
    return total === 0 ? 0 : this.page * this.pageSize + 1;
  }

  get endResult(): number {
    return Math.min(
      (this.page + 1) * this.pageSize,
      this.pageData?.total ?? 0
    );
  }

  /** `CarregamentoOut` não traz o nome da transportadora — só
   *  `transportadora_id`. Junção no cliente com a lista já carregada em
   *  `ngOnInit`, mesma decisão de `occurrences.component.ts`. */
  carrierName(shipment: Shipment): string {
    const carrier = this.carriers.find(
      c => c.id === shipment.transportadora_id
    );
    return carrier?.name ?? `Transportadora #${shipment.transportadora_id}`;
  }

  formatDate(value: string | null): string {
    if (!value) return '—';

    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : new Intl.DateTimeFormat('pt-BR', {
          dateStyle: 'medium',
          timeStyle: 'short'
        }).format(date);
  }

  // --- criação de carregamento -------------------------------------------

  openCreateModal(): void {
    this.createForm.reset({ carrierId: null });
    this.createError = '';
    this.createdShipment = null;
    this.showCreateModal = true;
  }

  /** Fecha o modal de criação/credencial. É o único ponto que descarta
   *  `createdShipment` — depois disso a senha não existe mais em memória
   *  nenhuma, e não há como reabrir para consultá-la de novo. */
  closeCreateModal(): void {
    if (this.creating) return;

    const hadCreatedShipment = this.createdShipment !== null;
    this.showCreateModal = false;
    this.createdShipment = null;
    this.createError = '';

    if (hadCreatedShipment) {
      this.page = 0;
      this.loadPage();
    }
  }

  onCreateBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.closeCreateModal();
    }
  }

  submitCreate(): void {
    if (this.createForm.invalid || this.creating) {
      this.createForm.markAllAsTouched();
      return;
    }

    this.creating = true;
    this.createError = '';

    const carrierId = this.createForm.getRawValue().carrierId as number;

    this.shipmentService.createShipment(carrierId).subscribe({
      next: created => {
        this.creating = false;
        this.createdShipment = created;
        this.cdr.markForCheck();
      },
      error: error => {
        this.creating = false;
        this.createError = backendDetail(
          error,
          'Não foi possível criar o carregamento.'
        );
        this.cdr.markForCheck();
      }
    });
  }

  // --- atribuição de pedido ------------------------------------------------

  openAssign(shipment: Shipment): void {
    this.assigningShipment = shipment;
    this.assignError = '';
    this.assignForm.reset({ orderId: '' });
    this.loadOrders(shipment.id);
  }

  closeAssign(): void {
    if (this.assigning) return;

    this.assigningShipment = null;
    this.shipmentOrders = [];
    this.assignError = '';
  }

  onAssignBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.closeAssign();
    }
  }

  loadOrders(shipmentId: number): void {
    this.loadingOrders = true;

    this.shipmentService.listOrders(shipmentId).subscribe({
      next: orders => {
        this.shipmentOrders = orders;
        this.loadingOrders = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.loadingOrders = false;
        this.cdr.markForCheck();
      }
    });
  }

  submitAssign(): void {
    if (
      this.assignForm.invalid ||
      this.assigning ||
      !this.assigningShipment
    ) {
      this.assignForm.markAllAsTouched();
      return;
    }

    const shipmentId = this.assigningShipment.id;
    const orderId = this.assignForm.getRawValue().orderId.trim();

    this.assigning = true;
    this.assignError = '';

    this.shipmentService.assignOrder(shipmentId, orderId).subscribe({
      next: () => {
        this.assigning = false;
        this.assignForm.reset({ orderId: '' });
        this.loadOrders(shipmentId);
        this.showSuccess('Pedido atribuído ao carregamento.');
      },
      error: error => {
        this.assigning = false;
        // A sentença do 409 (origem divergente / pedido já atribuído) é do
        // servidor — exibida verbatim, sem reescrever (ver http-error.ts).
        this.assignError = backendDetail(
          error,
          'Não foi possível atribuir o pedido a este carregamento.'
        );
        this.cdr.markForCheck();
      }
    });
  }

  private showSuccess(message: string): void {
    this.successMessage = message;

    if (this.successTimer !== null) {
      window.clearTimeout(this.successTimer);
    }

    this.successTimer = window.setTimeout(() => {
      this.successMessage = '';
      this.successTimer = null;
      this.cdr.markForCheck();
    }, 3200);

    this.cdr.markForCheck();
  }
}
