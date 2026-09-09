import { CommonModule } from '@angular/common';
import {
  ChangeDetectorRef,
  Component,
  EventEmitter,
  Input,
  Output,
  inject
} from '@angular/core';

import {
  Occurrence,
  OccurrenceType
} from '../../core/models/occurrence.model';
import { OccurrenceService } from '../../core/services/occurrence.service';

@Component({
  selector: 'app-occurrence-detail-modal',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './occurrence-detail-modal.component.html',
  styleUrl: './occurrence-detail-modal.component.scss'
})
export class OccurrenceDetailModalComponent {
  private readonly occurrenceService = inject(OccurrenceService);
  private readonly cdr = inject(ChangeDetectorRef);

  @Input({ required: true }) occurrence!: Occurrence;
  @Input() carrierName = '—';

  @Output() closed = new EventEmitter<void>();
  @Output() updated = new EventEmitter<void>();

  saving = false;

  close(): void {
    if (!this.saving) this.closed.emit();
  }

  /** Só fecha (ABERTA -> RESOLVIDA). Não existe "reabrir" no backend —
   *  `POST /occurrences/{id}/close` é uma via só, diferente do toggle
   *  bidirecional que a tela tinha contra a API Java. */
  resolve(): void {
    if (this.occurrence.status !== 'ABERTA' || this.saving) return;

    this.saving = true;

    this.occurrenceService.close(this.occurrence.id).subscribe({
      next: () => {
        this.saving = false;
        this.cdr.markForCheck();
        this.updated.emit();
      },
      error: () => {
        this.saving = false;
        this.cdr.markForCheck();
      }
    });
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

  formatDate(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : new Intl.DateTimeFormat('pt-BR', {
          dateStyle: 'medium',
          timeStyle: 'short'
        }).format(date);
  }

  onBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) this.close();
  }
}
