import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';

import { Carrier } from '../../core/models/carrier.model';
import {
  Occurrence,
  OccurrenceList,
  OccurrenceStatus,
  OccurrenceType
} from '../../core/models/occurrence.model';
import { CarrierService } from '../../core/services/carrier.service';
import { OccurrenceService } from '../../core/services/occurrence.service';
import { OccurrenceDetailModalComponent } from '../../shared/occurrence-detail-modal/occurrence-detail-modal.component';

@Component({
  selector: 'app-occurrences',
  standalone: true,
  imports: [CommonModule, OccurrenceDetailModalComponent],
  templateUrl: './occurrences.component.html',
  styleUrl: './occurrences.component.scss'
})
export class OccurrencesComponent implements OnInit {
  private readonly occurrenceService = inject(OccurrenceService);
  private readonly carrierService = inject(CarrierService);
  private readonly cdr = inject(ChangeDetectorRef);

  pageData: OccurrenceList | null = null;
  carriers: Carrier[] = [];
  selectedOccurrence: Occurrence | null = null;

  page = 0;
  readonly pageSize = 3;

  carrierId: number | null = null;
  type: OccurrenceType | '' = '';
  status: OccurrenceStatus | '' = '';

  loading = true;

  ngOnInit(): void {
    this.carrierService.getAllCarriers().subscribe(carriers => {
      this.carriers = carriers;
      this.cdr.markForCheck();
    });

    this.loadPage();
  }

  loadPage(): void {
    this.loading = true;

    this.occurrenceService
      .listOccurrences(
        this.pageSize,
        this.page * this.pageSize,
        this.carrierId,
        this.type,
        this.status
      )
      .subscribe({
        next: page => {
          this.pageData = page;
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.loading = false;
          this.cdr.markForCheck();
        }
      });
  }

  carrierChanged(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.carrierId = value ? Number(value) : null;
    this.resetAndLoad();
  }

  typeChanged(event: Event): void {
    this.type = (event.target as HTMLSelectElement)
      .value as OccurrenceType | '';
    this.resetAndLoad();
  }

  statusChanged(event: Event): void {
    this.status = (event.target as HTMLSelectElement)
      .value as OccurrenceStatus | '';
    this.resetAndLoad();
  }

  resetAndLoad(): void {
    this.page = 0;
    this.loadPage();
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

  /** `OcorrenciaOut` não traz o nome da transportadora — só
   *  `transportadora_id`. Junção no cliente com a lista já carregada em
   *  `ngOnInit`, mesma decisão do estoque (produtos-stock). */
  carrierName(occurrence: Occurrence): string {
    if (occurrence.transportadora_id === null) return '—';
    const carrier = this.carriers.find(
      c => c.id === occurrence.transportadora_id
    );
    return carrier?.name ?? `Transportadora #${occurrence.transportadora_id}`;
  }

  typeLabel(type: OccurrenceType): string {
    switch (type) {
      case 'DANO':
        return 'Dano';
      case 'ATRASO_ENTREGA':
        return 'Atraso';
      case 'FALHA_ENTREGA':
        return 'Falha na entrega';
      case 'FALTA_ESTOQUE':
        return 'Falta de estoque';
      default:
        return 'Outro';
    }
  }

  typeClass(type: OccurrenceType): string {
    switch (type) {
      case 'DANO':
        return 'damage';
      case 'FALHA_ENTREGA':
        return 'failure';
      case 'ATRASO_ENTREGA':
        return 'delay';
      // `.type-badge` só define damage/delay/failure/other
      // (occurrences.component.scss) — sem uma classe `.shortage`, a
      // badge de FALTA_ESTOQUE ficava sem nenhum estilo aplicado. Mapear
      // para 'other' evita mudar SCSS (que já geraria risco de um quarto
      // aviso de budget) e ainda é o rótulo visualmente correto: FALTA_
      // ESTOQUE é o único tipo aqui que não é fim-de-transportadora.
      case 'FALTA_ESTOQUE':
      default:
        return 'other';
    }
  }

  statusLabel(status: OccurrenceStatus): string {
    return status === 'ABERTA' ? 'ABERTA' : 'RESOLVIDA';
  }

  formatDate(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;

    const month = new Intl.DateTimeFormat('pt-BR', {
      month: 'short'
    }).format(date).replace('.', '');

    return `${String(date.getDate()).padStart(2, '0')} ${month.charAt(0).toUpperCase() + month.slice(1)}\n${date.getFullYear()}`;
  }

  occurrenceUpdated(): void {
    this.selectedOccurrence = null;
    this.loadPage();
  }
}
