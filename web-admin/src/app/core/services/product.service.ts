import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { EMPTY, expand, map, Observable, reduce } from 'rxjs';

import {
  CreateProductRequest,
  Product,
  ProductList,
  UpdateProductRequest
} from '../models/product.model';

export interface ProductPageResult {
  items: Product[];
  /** `true` quando o corte de segurança (`MAX_ITEMS`) foi atingido antes do
   *  fim real do catálogo. */
  truncated: boolean;
}

@Injectable({ providedIn: 'root' })
export class ProductService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  /** Teto da rota (`produtos.py`, `limit: int = Query(..., le=100)`) — a
   *  maior página que o backend aceita por chamada. */
  private static readonly PAGE_LIMIT = 100;
  /** Mesmo corte de segurança de `InventoryService.listAllInventory` —
   *  folga generosa, não limite de negócio. */
  private static readonly MAX_ITEMS = 2000;

  listProducts(limit = ProductService.PAGE_LIMIT, offset = 0): Observable<ProductList> {
    const params = new HttpParams()
      .set('limit', String(limit))
      .set('offset', String(offset));

    return this.http.get<ProductList>(`${this.apiUrl}/products`, { params });
  }

  /** Pagina `GET /products` até vir uma página mais curta que `PAGE_LIMIT`
   *  ou até `MAX_ITEMS`. `GET /products` ordena por nome e `GET
   *  /admin/inventory` ordena por id de estoque — as duas janelas não têm
   *  relação nenhuma, então uma única chamada com `limit=100` para juntar
   *  produto↔estoque (ver products-stock.component.ts) quebra assim que o
   *  CATÁLOGO passa de 100 produtos, por menor que seja o estoque: linhas
   *  afetadas mostram "Produto não encontrado", SKU "—", saem do filtro de
   *  nome/SKU e ganham a imagem placeholder errada. Não há filtro `ids`
   *  nessa rota — paginar é a única saída. */
  listAllProducts(): Observable<ProductPageResult> {
    const pageLimit = ProductService.PAGE_LIMIT;
    const maxItems = ProductService.MAX_ITEMS;

    return this.listProducts(pageLimit, 0).pipe(
      map(page => ({ page: page.items, offset: 0 })),
      expand(({ page, offset }) => {
        const nextOffset = offset + pageLimit;
        const pageWasFull = page.length === pageLimit;

        if (!pageWasFull || nextOffset >= maxItems) {
          return EMPTY;
        }

        return this.listProducts(pageLimit, nextOffset).pipe(
          map(nextPage => ({ page: nextPage.items, offset: nextOffset }))
        );
      }),
      reduce(
        (acc, { page, offset }) => ({
          items: [...acc.items, ...page],
          truncated:
            acc.truncated ||
            (page.length === pageLimit && offset + pageLimit >= maxItems)
        }),
        { items: [] as Product[], truncated: false as boolean }
      )
    );
  }

  getProduct(productId: string): Observable<Product> {
    return this.http.get<Product>(`${this.apiUrl}/products/${productId}`);
  }

  createProduct(request: CreateProductRequest): Observable<Product> {
    return this.http.post<Product>(`${this.apiUrl}/products`, request);
  }

  updateProduct(
    productId: string,
    request: UpdateProductRequest
  ): Observable<Product> {
    return this.http.put<Product>(
      `${this.apiUrl}/products/${productId}`,
      request
    );
  }
}
