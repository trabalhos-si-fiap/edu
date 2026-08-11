#!/usr/bin/env python3
"""Prepare the demo data used by scripts/demo-telas.sh.

Guarantees, through the API gateway (never straight into the database, so
the seed itself exercises the same path the app takes):

  - four users: student, picker, deliverer and admin, all with the same
    password;
  - one saved address for the student, so the staff screens have something
    to show in the order subtitle;
  - at least one order sitting in AGUARDANDO_SEPARACAO, which is what the
    picker's queue lists;
  - at least one order sitting in AGUARDANDO_COLETA, which is what the
    deliverer's queue lists.

Idempotent, and safe to run before every demo: it only creates what is
missing. The demo advances orders through the flow (the picker starts a
separation, for one), so re-running this before each take is what keeps
both queues populated.

The three staff roles are promoted with SQL because POST /auth/register is
public and always writes role='student', while POST /auth/register-staff
requires an existing admin — and a fresh database has none.

Exit codes: 0 ready, 1 something failed (message on stderr).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

SENHA = "Teste@123"

# (e-mail, nome, papel). O papel 'student' é o que o cadastro público já
# grava; os outros três são aplicados por SQL logo depois.
USERS = [
    ("aluno@teste.com", "Aluno Teste", "student"),
    ("separador@teste.com", "Separador Teste", "separador"),
    ("entregador@teste.com", "Entregador Teste", "entregador"),
    ("admin@teste.com", "Admin Teste", "admin"),
]

ENDERECO = {
    "label": "Casa",
    "zip_code": "01310-100",
    "street": "Avenida Paulista",
    "number": "1578",
    "complement": "Apto 42",
    "neighborhood": "Bela Vista",
    "city": "Sao Paulo",
    "state": "SP",
    "is_favorite": True,
}


class SeedError(RuntimeError):
    pass


def call(base, method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{base}{path}", data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode()
            return res.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except urllib.error.URLError as exc:
        raise SeedError(f"gateway inacessivel em {base}: {exc.reason}") from exc


def lista(body):
    """`GET /products` devolve um envelope paginado; os demais devolvem
    array cru. Normaliza os dois para lista."""
    if isinstance(body, dict) and "items" in body:
        return body["items"]
    return body if isinstance(body, list) else []


def psql(container, sql):
    resultado = subprocess.run(
        ["docker", "exec", "-i", container, "psql", "-U", "edu", "-d", "auth_db", "-tAc", sql],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise SeedError(f"psql falhou: {resultado.stderr.strip()}")
    return resultado.stdout.strip()


def garantir_usuarios(base, container):
    for email, nome, _ in USERS:
        status, corpo = call(
            base,
            "POST",
            "/auth/register",
            body={
                "name": nome,
                "email": email,
                "phone": "11999990000",
                "birth_date": "01/01/2000",
                "education_level": "Vestibulando",
                "password": SENHA,
            },
        )
        if status not in (201, 409):
            raise SeedError(f"register {email}: {status} {corpo}")

    for email, _, papel in USERS:
        if papel != "student":
            psql(container, f"UPDATE users SET role = '{papel}' WHERE email = '{email}';")

    tokens = {}
    for email, _, papel in USERS:
        status, corpo = call(base, "POST", "/auth/login", body={"email": email, "password": SENHA})
        if status != 200:
            raise SeedError(f"login {email}: {status} {corpo}")
        tokens[papel] = corpo["tokens"]["access_token"]
    return tokens


def garantir_endereco(base, token):
    status, corpo = call(base, "GET", "/auth/addresses", token)
    if status != 200:
        raise SeedError(f"listar enderecos: {status} {corpo}")
    enderecos = lista(corpo)
    if enderecos:
        return enderecos[0]["id"]
    status, corpo = call(base, "POST", "/auth/addresses", token, ENDERECO)
    if status != 201:
        raise SeedError(f"criar endereco: {status} {corpo}")
    return corpo["id"]


def criar_pedido_pago(base, tokens, address_id, itens=2):
    """Carrinho -> pedido -> pagamento confirmado. Termina em
    AGUARDANDO_SEPARACAO, que é o estado que a fila do separador lista."""
    status, corpo = call(base, "GET", "/products?limit=20", tokens["student"])
    produtos = lista(corpo)
    if status != 200 or not produtos:
        raise SeedError(
            f"catalogo vazio ({status}) — rode: docker compose exec -T "
            f"commerce-service uv run python -m app.seeds.products"
        )
    for produto in produtos[:itens]:
        status, corpo = call(
            base,
            "POST",
            "/cart/items",
            tokens["student"],
            {"product_id": produto["id"], "quantity": 1},
        )
        if status != 201:
            raise SeedError(f"adicionar ao carrinho: {status} {corpo}")

    status, pedido = call(
        base,
        "POST",
        "/orders",
        tokens["student"],
        {"payment_method": "PIX", "address_id": address_id},
    )
    if status != 201:
        raise SeedError(f"criar pedido: {status} {pedido}")

    pedido_id = pedido["id"]
    status, corpo = call(
        base, "PATCH", f"/admin/orders/{pedido_id}/confirm-payment", tokens["admin"]
    )
    if status != 200:
        raise SeedError(f"confirmar pagamento: {status} {corpo}")
    return pedido_id


def tamanho_da_fila(base, token, path):
    status, corpo = call(base, "GET", path, token)
    if status != 200:
        raise SeedError(f"GET {path}: {status} {corpo}")
    return lista(corpo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8100/api")
    parser.add_argument("--postgres-container", default="edu-postgres")
    args = parser.parse_args()

    try:
        tokens = garantir_usuarios(args.base, args.postgres_container)
        address_id = garantir_endereco(args.base, tokens["student"])

        if not tamanho_da_fila(args.base, tokens["separador"], "/picking/queue"):
            pedido = criar_pedido_pago(args.base, tokens, address_id)
            print(f"  fila de separacao estava vazia; criei {pedido}")

        entrega = tamanho_da_fila(args.base, tokens["entregador"], "/delivery/queue")
        if not entrega:
            # Um segundo pedido, empurrado até AGUARDANDO_COLETA, para a
            # tela do entregador não abrir vazia. O primeiro fica onde está.
            pedido = criar_pedido_pago(args.base, tokens, address_id, itens=1)
            for path in (f"/picking/{pedido}/start", f"/picking/{pedido}/finish"):
                status, corpo = call(args.base, "PATCH", path, tokens["separador"])
                if status != 200:
                    raise SeedError(f"PATCH {path}: {status} {corpo}")
            print(f"  fila de entrega estava vazia; criei {pedido}")

        separacao = tamanho_da_fila(args.base, tokens["separador"], "/picking/queue")
        entrega = tamanho_da_fila(args.base, tokens["entregador"], "/delivery/queue")
        print(f"  fila de separacao: {len(separacao)} | fila de entrega: {len(entrega)}")
    except SeedError as exc:
        print(f"seed falhou: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
