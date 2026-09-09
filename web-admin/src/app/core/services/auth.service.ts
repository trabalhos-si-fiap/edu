import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { tap } from 'rxjs';

import { LoginResponse } from '../models/auth.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  private readonly apiUrl = '/api';
  private readonly tokenKey = 'edu_admin_token';
  private readonly userKey = 'edu_admin_user';

  login(email: string, password: string, remember: boolean) {
    return this.http
      .post<LoginResponse>(`${this.apiUrl}/auth/login`, { email, password })
      .pipe(
        tap(response => {
          this.clearStorages();

          // Só o access token e o usuário são persistidos. O painel não
          // implementa refresh — guardar um refresh_token de 14 dias em
          // localStorage/sessionStorage sem nenhum código que o use seria
          // superfície de ataque sem contrapartida (pendência: task 14).
          const storage = remember ? localStorage : sessionStorage;
          storage.setItem(this.tokenKey, response.tokens.access_token);
          storage.setItem(this.userKey, JSON.stringify(response.user));
        })
      );
  }

  getToken(): string | null {
    return (
      localStorage.getItem(this.tokenKey) ??
      sessionStorage.getItem(this.tokenKey)
    );
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  logout(): void {
    this.clearStorages();
  }

  private clearStorages(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
    sessionStorage.removeItem(this.tokenKey);
    sessionStorage.removeItem(this.userKey);
  }
}
