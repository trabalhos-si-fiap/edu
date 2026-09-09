/** Espelha `ProductOut` (commerce-service). `id` é UUID, não number;
 *  `price` chega como STRING — o backend serializa dinheiro como texto de
 *  propósito, para o cliente nunca herdar erro de arredondamento de float
 *  (ver `ProductOut._price_as_string`). Não existe mais `minimumStock`
 *  aqui: quantidade mínima vive no estoque (`inventory.model.ts`), não no
 *  produto. */
export interface Product {
  id: string;
  name: string;
  sku: string;
  type: string;
  subtype: string;
  description: string;
  price: string;
  active: boolean;
  image_url: string;
}

export interface ProductList {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}

/** Espelha `ProductIn`. `fornecedor_id` é obrigatório — todo produto
 *  pertence a um parceiro — e cria a linha de estoque no mesmo ato
 *  (`quantidade_inicial`, `estoque_minimo`). */
export interface CreateProductRequest {
  name: string;
  type: string;
  subtype: string;
  description: string;
  price: string;
  sku: string;
  active: boolean;
  fornecedor_id: number;
  quantidade_inicial: number;
  estoque_minimo: number;
}

/** Espelha `ProductPatch`. Edição de catálogo NÃO mexe em estoque —
 *  quantidade só muda por ajuste auditado (`POST
 *  /products/{id}/stock-adjustments` ou `PATCH
 *  /admin/inventory/{id}/adjust`). Não há hoje nenhuma rota para editar
 *  `estoque_minimo` depois da criação (pendência: task 14). */
export type UpdateProductRequest = Omit<
  CreateProductRequest,
  'fornecedor_id' | 'quantidade_inicial' | 'estoque_minimo'
>;
