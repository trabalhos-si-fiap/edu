import { CommonModule } from '@angular/common';
import {
  ChangeDetectorRef,
  Component,
  DestroyRef,
  inject,
  OnInit
} from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { debounceTime, distinctUntilChanged, forkJoin } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import {
  InventoryStockRow,
  InventorySummary,
  inventoryStatus
} from '../../core/models/inventory.model';
import { InventoryService } from '../../core/services/inventory.service';
import { ProductService } from '../../core/services/product.service';
import { ProductFormModalComponent } from '../../shared/product-form-modal/product-form-modal.component';
import { StockAdjustModalComponent } from '../../shared/stock-adjust-modal/stock-adjust-modal.component';
import { SuccessToastComponent } from '../../shared/success-toast/success-toast.component';

@Component({
  selector: 'app-products-stock',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    ProductFormModalComponent,
    StockAdjustModalComponent,
    SuccessToastComponent
  ],
  templateUrl: './products-stock.component.html',
  styleUrl: './products-stock.component.scss'
})
export class ProductsStockComponent implements OnInit {
  private readonly inventoryService = inject(InventoryService);
  private readonly productService = inject(ProductService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly cdr = inject(ChangeDetectorRef);

  readonly searchControl = new FormControl('', { nonNullable: true });

  /** Todas as linhas (estoque + produto, junção no cliente — ver
   *  inventory.model.ts), antes de filtro e paginação, também aplicados no
   *  cliente por falta de `search`/`lowStock` no backend. */
  private allRows: InventoryStockRow[] = [];
  filteredRows: InventoryStockRow[] = [];
  pageRows: InventoryStockRow[] = [];

  summary: InventorySummary = {
    totalProducts: 0,
    lowStock: 0,
    outOfStock: 0
  };

  page = 0;
  readonly pageSize = 3;
  lowStockOnly = false;

  /** `true` só quando `InventoryService.listAllInventory()` bateu no corte
   *  de segurança (2000 linhas) antes do fim real dos dados — nesse caso a
   *  tela avisa, em vez de fingir que viu tudo. */
  inventoryTruncated = false;

  loadingTable = false;
  loadingSummary = false;

  selectedStockItem: InventoryStockRow | null = null;
  productFormOpen = false;
  editingProductId: string | null = null;

  successMessage = '';
  private successTimer: number | null = null;

  ngOnInit(): void {
    this.loadSummary();
    this.loadAll();

    this.searchControl.valueChanges
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => {
        this.page = 0;
        this.applyFilters();
      });
  }

  loadAll(): void {
    this.loadingTable = true;

    forkJoin({
      inventory: this.inventoryService.listAllInventory(),
      products: this.productService.listAllProducts()
    }).subscribe({
      next: ({ inventory, products }) => {
        const productById = new Map(products.items.map(p => [p.id, p]));

        this.allRows = inventory.items.map(item => {
          const product = productById.get(item.produto_id);
          return {
            ...item,
            productName: product?.name ?? 'Produto não encontrado',
            sku: product?.sku ?? '—',
            status: inventoryStatus(item)
          };
        });

        this.inventoryTruncated = inventory.truncated;
        this.page = 0;
        this.applyFilters();
        this.loadingTable = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.loadingTable = false;
        this.cdr.markForCheck();
      }
    });
  }

  applyFilters(): void {
    const term = this.searchControl.value.trim().toLowerCase();

    this.filteredRows = this.allRows.filter(row => {
      const matchesSearch =
        !term ||
        row.productName.toLowerCase().includes(term) ||
        row.sku.toLowerCase().includes(term);
      const matchesLowStock = !this.lowStockOnly || row.status !== 'NORMAL';
      return matchesSearch && matchesLowStock;
    });

    this.paginate();
  }

  loadSummary(): void {
    this.loadingSummary = true;

    this.inventoryService.getSummary().subscribe({
      next: summary => {
        this.summary = summary;
        this.loadingSummary = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.loadingSummary = false;
        this.cdr.markForCheck();
      }
    });
  }

  openNewProduct(): void {
    this.editingProductId = null;
    this.productFormOpen = true;
  }

  openEditProduct(item: InventoryStockRow): void {
    this.editingProductId = item.produto_id;
    this.productFormOpen = true;
  }

  closeProductForm(): void {
    this.productFormOpen = false;
    this.editingProductId = null;
  }

  productSaved(mode: 'created' | 'updated'): void {
    this.closeProductForm();
    this.loadAll();
    this.loadSummary();

    this.showSuccess(
      mode === 'created'
        ? 'Produto adicionado com sucesso'
        : 'Produto editado com sucesso'
    );
  }

  openAdjust(item: InventoryStockRow): void {
    this.selectedStockItem = item;
  }

  closeAdjust(): void {
    this.selectedStockItem = null;
  }

  afterAdjusted(): void {
    this.selectedStockItem = null;
    this.loadAll();
    this.loadSummary();
  }

  toggleLowStock(event: Event): void {
    this.lowStockOnly = (event.target as HTMLInputElement).checked;
    this.page = 0;
    this.applyFilters();
  }

  previousPage(): void {
    if (this.page <= 0) return;
    this.page--;
    this.paginate();
  }

  nextPage(): void {
    if (this.page + 1 >= this.totalPages) return;
    this.page++;
    this.paginate();
  }

  goToDisplayPage(displayPage: number): void {
    this.page = displayPage - 1;
    this.paginate();
  }

  statusLabel(item: InventoryStockRow): string {
    switch (item.status) {
      case 'LOW_STOCK':
        return 'Baixo';
      case 'OUT_OF_STOCK':
        return 'Esgotado';
      default:
        return 'Adequado';
    }
  }

  statusClass(item: InventoryStockRow): string {
    switch (item.status) {
      case 'LOW_STOCK':
        return 'low';
      case 'OUT_OF_STOCK':
        return 'out';
      default:
        return 'normal';
    }
  }

  productImage(item: InventoryStockRow): string {
    const name = item.productName.toLowerCase();

    if (
      name.includes('bloco') ||
      name.includes('caneta') ||
      name.includes('kit')
    ) {
      return '/assets/images/product-blocks.png';
    }

    if (
      item.status === 'OUT_OF_STOCK' ||
      name.includes('tablet')
    ) {
      return '/assets/images/product-tablet.png';
    }

    return '/assets/images/product-book.png';
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.filteredRows.length / this.pageSize));
  }

  get displayPages(): number[] {
    const total = this.totalPages;
    if (this.filteredRows.length === 0) return [];

    const current = this.page + 1;

    if (total === 1) return [1];
    if (current === total) return [Math.max(1, current - 1), current];

    return [current, current + 1];
  }

  get startResult(): number {
    const total = this.filteredRows.length;
    return total === 0 ? 0 : this.page * this.pageSize + 1;
  }

  get endResult(): number {
    return Math.min((this.page + 1) * this.pageSize, this.filteredRows.length);
  }

  get totalResults(): number {
    return this.filteredRows.length;
  }

  get hasPrevious(): boolean {
    return this.page > 0;
  }

  get hasNext(): boolean {
    return this.page + 1 < this.totalPages;
  }

  private paginate(): void {
    const start = this.page * this.pageSize;
    this.pageRows = this.filteredRows.slice(start, start + this.pageSize);
    this.cdr.markForCheck();
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
