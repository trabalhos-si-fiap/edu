#!/usr/bin/env bash
#
# Demonstração gravável das três telas de staff: separador, entregador e
# admin. Sobe o backend se estiver fora do ar, semeia os dados, instala o
# app num Android conectado e passa pelas três telas sozinho, rolando cada
# uma de ponta a ponta. Faz login e logout, e nada além disso: não toca em
# card, botão ou aba, para a passagem ser curta.
#
# Uso:
#   scripts/demo-telas.sh                 # tudo: backend, seed, build, demo
#   scripts/demo-telas.sh --skip-build    # reaproveita o APK já instalado
#   scripts/demo-telas.sh --only admin    # uma tela só (separador|entregador|admin)
#   scripts/demo-telas.sh --pausa 4       # mais lento, para gravar com calma
#
# Antes de gravar: deixe o celular desbloqueado, com rotação travada em
# retrato e a barra de notificação limpa.
#
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONT="$RAIZ/front-end-flutter"
BACK="$RAIZ/back-end"

PACOTE="br.com.fiap.estuda_app"
ATIVIDADE="$PACOTE/.MainActivity"
SENHA="Teste@123"

# Porta externa do gateway (o app fala com o gateway, nunca com o legacy).
# Lida do .env compartilhado; o default 8100 é o mesmo do docker-compose.yml.
PORTA_GATEWAY="$(sed -n 's/^GATEWAY_PORT_EXTERNAL=//p' "$BACK/.env" 2>/dev/null | tr -d '[:space:]')"
PORTA_GATEWAY="${PORTA_GATEWAY:-8100}"

PAUSA=3
PULAR_BUILD=0
SOMENTE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build) PULAR_BUILD=1; shift ;;
    --pausa) PAUSA="$2"; shift 2 ;;
    --only) SOMENTE="$2"; shift 2 ;;
    -h|--help) sed -n '2,${/^#/!q;p;}' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
done

titulo() { printf '\n\033[1;35m▸ %s\033[0m\n' "$*"; }
passo()  { printf '  \033[0;36m·\033[0m %s\n' "$*"; }
erro()   { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ── Pré-requisitos ────────────────────────────────────────────────────

for binario in adb docker python3; do
  command -v "$binario" >/dev/null || erro "$binario não está no PATH"
done

FLUTTER="${FLUTTER:-$(command -v flutter || true)}"
if [[ -z "$FLUTTER" ]]; then
  for p in "$HOME/flutter/bin/flutter" "$HOME/Documents/flutter/bin/flutter" \
           "$HOME/development/flutter/bin/flutter" "/opt/flutter/bin/flutter"; do
    [[ -x "$p" ]] && { FLUTTER="$p"; break; }
  done
fi
[[ -n "$FLUTTER" ]] || erro "flutter não encontrado — exporte FLUTTER=/caminho/para/flutter"

DISPOSITIVO="$(adb devices | awk '$2=="device"{print $1}' | head -1)"
[[ -n "$DISPOSITIVO" ]] || erro "nenhum Android autorizado no adb (rode: adb devices)"

# IP do host na LAN: é contra ele que o app e as URLs assinadas das fotos
# de produto apontam. O alias 10.0.2.2 do api_config.dart só vale para o
# emulador; num aparelho físico ele não resolve para lugar nenhum.
IP_HOST="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
[[ -n "$IP_HOST" ]] || erro "não consegui detectar o IP do host na LAN"
BASE_API="http://$IP_HOST:$PORTA_GATEWAY/api"

# ── Backend ───────────────────────────────────────────────────────────

gateway_no_ar() {
  curl -sf -m 5 -o /dev/null "http://localhost:$PORTA_GATEWAY/health"
}

subir_backend() {
  titulo "Backend"
  if gateway_no_ar; then
    passo "gateway já responde em :$PORTA_GATEWAY"
  else
    passo "gateway fora do ar — subindo o stack"

    # O edu-minio publica 9000/9001. Se outro projeto já segurar a porta, o
    # commerce-service não sobe (depends_on: minio) e as fotos de produto
    # ficam inalcançáveis pelo celular, porque as URLs são assinadas contra
    # http://$IP_HOST:9000.
    local dono
    dono="$(docker ps --format '{{.Names}} {{.Ports}}' | awk '/0.0.0.0:9000/{print $1}' | grep -v '^edu-minio' || true)"
    if [[ -n "$dono" ]]; then
      erro "a porta 9000 está com o container '$dono' (outro projeto).
    Libere com:  docker stop $dono
    Devolva depois com:  docker stop edu-minio-1 && docker start $dono"
    fi

    (cd "$BACK" && HOST_IP="$IP_HOST" docker compose up -d \
      api-gateway auth-users-service learning-service commerce-service \
      notification-service analytics-service chatbot-service >/dev/null)

    passo "esperando o gateway responder"
    for _ in $(seq 1 60); do
      gateway_no_ar && break
      sleep 2
    done
    gateway_no_ar || erro "o gateway não subiu — veja: cd $BACK && docker compose logs api-gateway"
  fi

  # Catálogo vazio deixa as três telas sem nada para mostrar, e o seed dos
  # pedidos falha logo depois. É idempotente, então roda sempre.
  passo "conferindo o catálogo"
  (cd "$BACK" && docker compose exec -T commerce-service \
    uv run python -m app.seeds.products >/dev/null 2>&1) \
    || passo "seed do catálogo não rodou (siga se o catálogo já existir)"

  passo "preparando usuários e pedidos"
  python3 "$RAIZ/scripts/demo_seed.py" --base "http://localhost:$PORTA_GATEWAY/api" \
    || erro "o seed falhou — a demonstração ficaria com telas vazias"
}

# ── App ───────────────────────────────────────────────────────────────

instalar_app() {
  titulo "App"
  if [[ "$PULAR_BUILD" == "1" ]]; then
    adb shell pm list packages | grep -q "$PACOTE" \
      || erro "--skip-build pedido, mas $PACOTE não está instalado"
    passo "reaproveitando o APK já instalado"
    return
  fi
  # DEMO_ITENS_MOCK enche a checklist do separador com itens de vitrine. É
  # necessário porque nenhum schema de staff do Commerce Service devolve a
  # chave `itens`, e sem ela a tela grava um aviso técnico no lugar dos
  # produtos. Vale só nesta build — ver lib/features/logistics/data/demo_itens.dart.
  passo "compilando com API_BASE_URL=$BASE_API (+ itens de vitrine)"
  (cd "$FRONT" && "$FLUTTER" build apk --debug \
    --dart-define="API_BASE_URL=$BASE_API" \
    --dart-define=DEMO_ITENS_MOCK=true >/dev/null)
  passo "instalando em $DISPOSITIVO"
  adb -s "$DISPOSITIVO" install -r "$FRONT/build/app/outputs/flutter-apk/app-debug.apk" >/dev/null
}

# ── Gestos ────────────────────────────────────────────────────────────

# As frações abaixo foram medidas num 1080x2400 e convertidas para a
# resolução real do aparelho, de modo que a demonstração não fique presa a
# um modelo só. Telas muito fora de 20:9 podem exigir ajuste.
LARGURA=0; ALTURA=0
medir_tela() {
  local tamanho
  tamanho="$(adb -s "$DISPOSITIVO" shell wm size | tr -d '\r' | awk -F'[: x]+' '{print $(NF-1), $NF}')"
  LARGURA="$(echo "$tamanho" | cut -d' ' -f1)"
  ALTURA="$(echo "$tamanho" | cut -d' ' -f2)"
  passo "tela ${LARGURA}x${ALTURA}"
}

px() { python3 -c "print(int($LARGURA * $1))"; }
py() { python3 -c "print(int($ALTURA * $1))"; }

# Toque cego é perigoso: se uma tela não abriu, o toque seguinte cai em cima
# do que estiver na frente — launcher, outro app, o que for. Por isso todo
# toque confere antes se o app ainda tem o foco, e aborta na hora se não
# tiver, em vez de sair mexendo no aparelho de quem está gravando.
app_em_foco() {
  adb -s "$DISPOSITIVO" shell dumpsys window 2>/dev/null | grep -q "mCurrentFocus.*$PACOTE"
}

exigir_app() {
  app_em_foco && return 0
  erro "o app saiu de primeiro plano antes de '$1'.
    Abortei para não tocar em mais nada. Reabra e rode de novo."
}

toque() {
  exigir_app "${4:-toque}"
  adb -s "$DISPOSITIVO" shell input tap "$(px "$1")" "$(py "$2")"
  sleep "${3:-1}"
}

digitar() { adb -s "$DISPOSITIVO" shell input text "$1"; sleep 1; }

teclado_aberto() {
  adb -s "$DISPOSITIVO" shell dumpsys input_method 2>/dev/null | grep -q "mInputShown=true"
}

# `keyevent 4` com o teclado aberto fecha o teclado; com o teclado fechado
# ele VOLTA — e voltar na tela de fila sai do app. Foi assim que uma
# execução anterior acabou tocando no launcher. Só mandamos a tecla depois
# de confirmar que há teclado para fechar.
fechar_teclado() {
  teclado_aberto || return 0
  adb -s "$DISPOSITIVO" shell input keyevent 111   # ESC
  sleep 1
  teclado_aberto || return 0
  adb -s "$DISPOSITIVO" shell input keyevent 4
  sleep 1
}

# Rolagem lenta de propósito: numa gravação, um swipe rápido vira um borrão.
# Guardadas pelo mesmo motivo dos toques — um swipe fora do app rola a tela
# inicial de quem está gravando.
rolar() {
  exigir_app "rolagem"
  adb -s "$DISPOSITIVO" shell input swipe "$(px 0.5)" "$(py "$1")" "$(px 0.5)" "$(py "$2")" 900
  sleep 2
}
rolar_baixo() { rolar 0.75 0.30; }
rolar_cima()  { rolar 0.30 0.75; }

percorrer_tela() {
  local voltas="${1:-2}"
  for _ in $(seq 1 "$voltas"); do rolar_baixo; done
  sleep "$PAUSA"
  for _ in $(seq 1 "$voltas"); do rolar_cima; done
  sleep 1
}

# ── Login / logout ────────────────────────────────────────────────────

entrar_como() {
  local email="$1"
  toque 0.50 0.44 1 "campo de e-mail"
  digitar "$email"
  toque 0.50 0.57 1 "campo de senha"
  digitar "$SENHA"
  fechar_teclado            # com o teclado fora, o formulário volta à posição
  toque 0.50 0.65 8 "botão Entrar"
  exigir_app "a tela pós-login"
}

sair() {
  toque 0.91 0.072 5 "logout na AppBar"
}

abrir_app_limpo() {
  adb -s "$DISPOSITIVO" shell am force-stop "$PACOTE"
  sleep 1
  adb -s "$DISPOSITIVO" shell am start -n "$ATIVIDADE" >/dev/null
  sleep 12
  exigir_app "a abertura do app"
}

# ── Roteiros ──────────────────────────────────────────────────────────

demo_separador() {
  titulo "Tela 1 — Separador  (/picking/*, commerce-service)"
  passo "entrando como separador@teste.com"
  entrar_como "separador@teste.com"
  passo "Fila de Separação"
  percorrer_tela 1
  sleep "$PAUSA"
  passo "saindo"
  sair
}

demo_entregador() {
  titulo "Tela 2 — Entregador  (/delivery/*, commerce-service)"
  passo "entrando como entregador@teste.com"
  entrar_como "entregador@teste.com"
  passo "Fila de Coleta"
  percorrer_tela 1
  sleep "$PAUSA"
  passo "saindo"
  sair
}

demo_admin() {
  titulo "Tela 3 — Admin  (/analytics/*, analytics-service)"
  passo "entrando como admin@teste.com"
  entrar_como "admin@teste.com"
  passo "Painel Administrativo — relatório executivo, KPIs e o gráfico"
  percorrer_tela 3
  sleep "$PAUSA"
  passo "saindo"
  sair
}

# ── Execução ──────────────────────────────────────────────────────────

subir_backend
instalar_app

titulo "Demonstração"
medir_tela
passo "grave a tela agora — a navegação começa em 5 segundos"
sleep 5

abrir_app_limpo

case "$SOMENTE" in
  separador)  demo_separador ;;
  entregador) demo_entregador ;;
  admin)      demo_admin ;;
  "")         demo_separador; sleep "$PAUSA"
              demo_entregador; sleep "$PAUSA"
              demo_admin ;;
  *) erro "--only aceita: separador, entregador ou admin" ;;
esac

titulo "Fim"
passo "credenciais: aluno@ / separador@ / entregador@ / admin@teste.com — senha $SENHA"
passo "rode de novo antes da próxima gravação: o seed repõe as duas filas"
