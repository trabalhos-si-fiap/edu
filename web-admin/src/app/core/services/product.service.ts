import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  CreateProductRequest,
  Product,
  ProductList,
  UpdateProductRequest
} from '../models/product.model';

@Injectable({ providedIn: 'root' })
export class ProductService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api';

  /** Usado pela tela de estoque para juntar `produto_id` com nome/SKU —
   *  `EstoqueOut` não traz nome de produto (ver inventory.service.ts). */
  listProducts(limit = 100, offset = 0): Observable<ProductList> {
    const params = new HttpParams()
      .set('limit', String(limit))
      .set('offset', String(offset));

    return this.http.get<ProductList>(`${this.apiUrl}/products`, { params });
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
