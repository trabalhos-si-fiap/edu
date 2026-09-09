export interface AuthUser {
  id: string; // UUID — auth-users-service usa UUID, não number
  name: string;
  email: string;
  role: string;
}

/** Espelha `AuthResponseOut` de auth-users-service (`POST /auth/login`):
 *  `{user, tokens}` — medido em
 *  back-end/auth-users-service/app/schemas/auth.py. Nunca o formato
 *  `{accessToken, tokenType, user}` que o painel assumia contra a API Java
 *  que a spec A eliminou. */
export interface LoginResponse {
  user: AuthUser;
  tokens: {
    access_token: string;
    refresh_token: string;
    token_type: string;
  };
}
