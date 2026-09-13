import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./pages/login/login.component').then(m => m.LoginComponent)
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./layout/admin-layout/admin-layout.component').then(
        m => m.AdminLayoutComponent
      ),
    children: [
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./pages/dashboard/dashboard.component').then(
            m => m.DashboardComponent
          )
      },
      {
        path: 'pedidos',
        loadComponent: () =>
          import('./pages/orders/orders.component').then(
            m => m.OrdersComponent
          )
      },
      {
        path: 'produtos-estoque',
        loadComponent: () =>
          import('./pages/products-stock/products-stock.component').then(
            m => m.ProductsStockComponent
          )
      },
      {
        path: 'transportadoras',
        loadComponent: () =>
          import('./pages/carriers/carriers.component').then(
            m => m.CarriersComponent
          )
      },
      {
        path: 'carregamentos',
        loadComponent: () =>
          import('./pages/shipments/shipments.component').then(
            m => m.ShipmentsComponent
          )
      },
      {
        path: 'ocorrencias',
        loadComponent: () =>
          import('./pages/occurrences/occurrences.component').then(
            m => m.OccurrencesComponent
          )
      },
      {
        path: '',
        pathMatch: 'full',
        redirectTo: 'dashboard'
      }
    ]
  },
  {
    path: '**',
    redirectTo: ''
  }
];
