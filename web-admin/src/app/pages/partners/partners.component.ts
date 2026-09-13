import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';

import { backendDetail } from '../../core/http-error';
import { Partner } from '../../core/models/partner.model';
import { InventoryService } from '../../core/services/inventory.service';
import { PartnerService } from '../../core/services/partner.service';

type PartnerFilter = 'all' | 'active' | 'inactive';

@Component({
  selector: 'app-partners',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './partners.component.html',
  styleUrl: './partners.component.scss'
})
export class PartnersComponent implements OnInit {
  private readonly partnerService = inject(PartnerService);
  private readonly inventoryService = inject(InventoryService);
  private readonly cdr = inject(ChangeDetectorRef);

  /** Lista inteira, antes de filtro e paginação — os dois acontecem no
   *  cliente (ver `PartnerService.listAllPartners`). */
  private allPartners: Partner[] = [];
  filteredPartners: Partner[] = [];

  filter: PartnerFilter = 'all';
  page = 0;
  readonly pageSize = 10;

  loading = true;
  loadError = '';

  /** Produtos por parceiro, contados nas linhas de estoque: `Estoque` é único
   *  no par `(produto_id, fornecedor_id)`, então cada linha é um produto
   *  daquele parceiro. `null` enquanto carrega, se a carga falhar ou se o
   *  estoque bateu no corte de segurança — nesses casos a coluna mostra "—"
   *  em vez de um número menor que o real. */
  productCounts: Map<number, number> | null = null;

  ngOnInit(): void {
    this.loadPartners();
    this.loadProductCounts();
  }

  loadPartners(): void {
    this.loading = true;
    this.loadError = '';

    this.partnerService.listAllPartners().subscribe({
      next: partners => {
        this.allPartners = partners;
        this.applyFilter();
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: error => {
        this.loadError = backendDetail(
          error,
          'Não foi possível carregar os parceiros.'
        );
        this.loading = false;
        this.cdr.markForCheck();
      }
    });
  }

  loadProductCounts(): void {
    this.inventoryService.listAllInventory().subscribe({
      next: inventory => {
        if (inventory.truncated) return;

        const counts = new Map<number, number>();
        for (const row of inventory.items) {
          counts.set(row.fornecedor_id, (counts.get(row.fornecedor_id) ?? 0) + 1);
        }

        this.productCounts = counts;
        this.cdr.markForCheck();
      },
      // A contagem é complemento: sem ela a coluna fica em "—" e a lista
      // de parceiros, que tem sua própria mensagem de erro, segue de pé.
      error: () => undefined
    });
  }

  filterChanged(event: Event): void {
    this.filter = (event.target as HTMLSelectElement).value as PartnerFilter;
    this.page = 0;
    this.applyFilter();
  }

  private applyFilter(): void {
    this.filteredPartners = this.allPartners.filter(
      partner =>
        this.filter === 'all' ||
        partner.ativo === (this.filter === 'active')
    );
  }

  get pagePartners(): Partner[] {
    const start = this.page * this.pageSize;
    return this.filteredPartners.slice(start, start + this.pageSize);
  }

  get totalCount(): number {
    return this.allPartners.length;
  }

  get activeCount(): number {
    return this.allPartners.filter(partner => partner.ativo).length;
  }

  get inactiveCount(): number {
    return this.totalCount - this.activeCount;
  }

  /** "Ativos (3)" só depois de carregar — antes disso o número seria um
   *  zero que não foi medido. */
  filterLabel(label: string, count: number): string {
    return this.loading || this.loadError ? label : `${label} (${count})`;
  }

  previous(): void {
    if (this.page <= 0) return;
    this.page--;
  }

  next(): void {
    if (!this.hasNext) return;
    this.page++;
  }

  get hasNext(): boolean {
    return (this.page + 1) * this.pageSize < this.filteredPartners.length;
  }

  get startResult(): number {
    return this.filteredPartners.length === 0
      ? 0
      : this.page * this.pageSize + 1;
  }

  get endResult(): number {
    return Math.min(
      (this.page + 1) * this.pageSize,
      this.filteredPartners.length
    );
  }

  productCount(partner: Partner): string {
    return this.productCounts
      ? String(this.productCounts.get(partner.id) ?? 0)
      : '—';
  }

  initials(name: string): string {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map(part => part.charAt(0))
      .join('')
      .toUpperCase();
  }
}
