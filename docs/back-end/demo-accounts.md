# Contas de demonstração

Quatro contas fixas, uma por papel, para conduzir a apresentação sem criar
usuário na hora. Criadas por
`back-end/auth-users-service/app/seeds/demo_accounts.py`.

| Papel | E-mail |
|---|---|
| `admin` | `admin@demo.edu` |
| `student` | `aluno@demo.edu` |
| `separador` | `separador@demo.edu` |
| `entregador` | `entregador@demo.edu` |

**A senha não está aqui, nem no código.** Ela vem de `DEMO_ACCOUNTS_PASSWORD`,
e o seed recusa rodar sem ela — precisa ter ao menos 8 caracteres e um
caractere especial, a mesma regra que `/auth/register` já exige de qualquer
cadastro.

`DEMO_ACCOUNTS_PASSWORD` não está em nenhum `docker-compose.yml` nem
`.env.example` — o container não a recebe sozinho. `docker compose exec` NÃO
repassa o ambiente de quem chama; o processo executado só enxerga o ambiente
com que o container nasceu (`env_file`) mais o que vier explícito em `-e`. Por
isso o comando abaixo passa a senha com `-e`, na hora do `exec` — é a única
forma que funciona sem recriar o container.

## Como o seed cria cada conta

O seed dirige a aplicação por `httpx.AsyncClient` sobre `ASGITransport` — o
mesmo caminho de código das rotas, sem rede, sem duplicar a montagem do
`User`. Três das quatro contas passam pela rota real de cadastro:

| Conta | Caminho |
|---|---|
| `admin@demo.edu` | INSERT direto (bootstrap — ver seção abaixo) |
| `aluno@demo.edu` | `POST /auth/register` |
| `separador@demo.edu` | `POST /auth/register-staff`, com o token do admin |
| `entregador@demo.edu` | `POST /auth/register-staff`, com o token do admin |

Passar pelas rotas de verdade importa: `/auth/register` publica
`student.created` e `/auth/register-staff` publica `staff.created` — sem
isso, learning-service e analytics-service nunca saberiam que o aluno de
demonstração existe, e telas que dependem desses eventos (tracker de estudo,
analytics) ficariam vazias na apresentação. Um `INSERT` direto também
deixaria `aluno@demo.edu` sem `telefone`, `data_nascimento` e `escolaridade`
— campos que `/auth/register` exige de qualquer cadastro real — tornando o
aluno de demonstração diferente de todo aluno de verdade.

## Rodar

```bash
docker compose -f back-end/docker-compose.yml exec -T \
  -e DEMO_ACCOUNTS_PASSWORD='...' \
  auth-users-service uv run python -m app.seeds.demo_accounts
```

(ou `make services-seed-demo DEMO_ACCOUNTS_PASSWORD='...'`, que roda o mesmo
comando.)

Em ambos os casos a senha fica brevemente visível na saída de `ps` do host
enquanto o `exec` roda — inerente a passar segredo por `-e` na linha de
comando, não um vazamento de log. Aceitável para uma senha de demonstração;
não é assim que uma senha de produção deveria circular.

Idempotente: rodar duas vezes não duplica nada e devolve zero contas criadas
na segunda passada. A checagem de quem já existe roda uma vez, no início —
o seed não depende do 409 de e-mail duplicado das rotas para isso.

## Por que o admin é diferente

Não existe caminho de rota para o primeiro admin — `/auth/register` sempre
cria `student`, `/auth/register-staff` exige um admin já autenticado. O seed
rompe esse ciclo do ovo e da galinha uma única vez, de forma visível: monta o
`User` de `admin@demo.edu` diretamente e comita, com um comentário no código
explicando por quê. É o único carve-out — as outras três contas nascem pelas
rotas reais, com o mesmo `hash_password` e as mesmas validações que qualquer
cadastro passa.

O `entregador` continua existindo aqui mesmo depois da spec C, que substitui a
conta de entregador por credencial de carregamento: a conta serve para
exercitar o caminho antigo enquanto ele não é removido.
