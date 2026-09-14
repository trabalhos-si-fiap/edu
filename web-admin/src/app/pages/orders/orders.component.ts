import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';

import { backendDetail } from '../../core/http-error';
import {
  ORDER_STATUS_LABELS,
  OrderStatus,
  StaffOrder
} from '../../core/models/order.model';
import { OrderService } from '../../core/services/order.service';
import { SuccessToastComponent } from '../../shared/success-toast/success-toast.component';

/** Os dois estados de onde `confirm-payment` sai (admin.py): de CRIADO a rota
 *  encadeia as duas transições; de CONFIRMADO ela retoma a segunda, depois de
 *  um publish que falhou no meio da primeira tentativa. De qualquer outro, o
 *  servidor responde 400 — o botão nem aparece. */
const CONFIRMABLE_STATUSES: ReadonlySet<string> = new Set([
  'CRIADO',
  'CONFIRMADO'
]);

const BRL = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL'
});

@Component({
  selector: 'app-orders',
  standalone: true,
  imports: [CommonModule, SuccessToastComponent],
  templateUrl: './orders.component.html',
  styleUrl: './orders.component.scss'
})
export class OrdersComponent implements OnInit {
  private readonly orderService = inject(OrderService);
  private readonly cdr = inject(ChangeDetectorRef);

  readonly statusOptions = Object.entries(ORDER_STATUS_LABELS);

  orders: StaffOrder[] = [];

  page = 0;
  readonly pageSize = 10;
  statusFilter: OrderStatus | '' = '';

  loading = true;
  loadError = '';

  // --- confirmação de pagamento --------------------------------------------
  confirmingOrder: StaffOrder | null = null;
  confirming = false;
  confirmError = '';

  successMessage = '';
  private successTimer: number | null = null;

  ngOnInit(): void {
    this.loadPage();
  }

  loadPage(): void {
    this.loading = true;
    this.loadError = '';

    this.orderService
      .listOrders(this.pageSize, this.page * this.pageSize, this.statusFilter)
      .subscribe({
        next: orders => {
          this.orders = orders;
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: error => {
          this.orders = [];
          this.loadError = backendDetail(
            error,
            'Não foi possível carregar os pedidos.'
          );
          this.loading = false;
          this.cdr.markForCheck();
        }
      });
  }

  statusChanged(event: Event): void {
    this.statusFilter = (event.target as HTMLSelectElement)
      .value as OrderStatus | '';
    this.page = 0;
    this.loadPage();
  }

  previous(): void {
    if (this.page <= 0 || this.loading) return;
    this.page--;
    this.loadPage();
  }

  next(): void {
    if (!this.hasNext) return;
    this.page++;
    this.loadPage();
  }

  /** A rota não devolve `total`: uma página cheia é o único sinal de que
   *  pode haver mais. Quando o número de pedidos é múltiplo exato de
   *  `pageSize`, a última "próxima" volta vazia — o estado vazio da tabela
   *  cobre esse caso, e "anterior" continua habilitado. */
  get hasNext(): boolean {
    return !this.loading && this.orders.length === this.pageSize;
  }

  get startResult(): number {
    return this.page * this.pageSize + 1;
  }

  get endResult(): number {
    return this.page * this.pageSize + this.orders.length;
  }

  /** Mesmo recorte do app ("Pedido #XXXXXXXX", `Pedido.idCurto` em
   *  front-end-flutter/lib/features/logistics/domain/order.dart). */
  shortId(order: StaffOrder): string {
    return order.id.slice(0, 8).toUpperCase();
  }

  statusLabel(status: string): string {
    return ORDER_STATUS_LABELS[status as OrderStatus] ?? status;
  }

  /** Agrupa os dez estados nas cinco etapas que o aluno enxerga
   *  (`STATUS_CONTRATO` em status_pedido.py) — cor por etapa, rótulo exato. */
  statusTone(status: string): string {
    switch (status) {
      case 'CRIADO':
      case 'CONFIRMADO':
        return 'pending';
      case 'AGUARDANDO_COLETA':
      case 'EM_TRANSITO':
        return 'shipping';
      case 'ENTREGUE':
        return 'delivered';
      case 'CANCELADO':
        return 'cancelled';
      default:
        return 'picking';
    }
  }

  canConfirm(order: StaffOrder): boolean {
    return CONFIRMABLE_STATUSES.has(order.status);
  }

  /** `total` chega como STRING (ver `StaffOrder`). */
  formatMoney(value: string): string {
    const amount = Number(value);
    return Number.isFinite(amount) ? BRL.format(amount) : value;
  }

  formatDate(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : new Intl.DateTimeFormat('pt-BR', {
          dateStyle: 'short',
          timeStyle: 'short'
        }).format(date);
  }

  // --- confirmação de pagamento --------------------------------------------

  openConfirm(order: StaffOrder): void {
    this.confirmingOrder = order;
    this.confirmError = '';
  }

  closeConfirm(): void {
    if (this.confirming) return;

    this.confirmingOrder = null;
    this.confirmError = '';
  }

  onConfirmBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.closeConfirm();
    }
  }

  submitConfirm(): void {
    if (!this.confirmingOrder || this.confirming) return;

    const orderId = this.confirmingOrder.id;
    this.confirming = true;
    this.confirmError = '';

    this.orderService.confirmPayment(orderId).subscribe({
      next: updated => {
        this.confirming = false;
        this.confirmingOrder = null;
        // Troca a linha pela resposta em vez de recarregar a página: com um
        // filtro de status ativo, recarregar faria o pedido sumir da lista
        // no exato momento em que o admin quer ver o que aconteceu com ele.
        this.orders = this.orders.map(order =>
          order.id === updated.id ? updated : order
        );
        this.showSuccess(
          `Pagamento do pedido #${this.shortId(updated)} confirmado.`
        );
      },
      error: error => {
        this.confirming = false;
        // O 400 ("Transição inválida: ...") aparece quando outro admin já
        // confirmou este pedido — a sentença é do servidor, exibida como
        // veio (ver http-error.ts).
        this.confirmError = backendDetail(
          error,
          'Não foi possível confirmar o pagamento deste pedido.'
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
