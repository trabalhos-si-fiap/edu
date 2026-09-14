"""As cenas do roteiro, na ordem da narração.

Cada cena espera a tela mostrar o que precisa antes de tocar — nada de
coordenada fixa nem de espera cega. `Roteiro.pausa()` é o respiro para a
narração; o tamanho vem de `--pausa`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime

from .preparo import CONTAS_STAFF, Backend
from .roteiro_dados import Questao, email_da_ana, escolher_alternativa, proximo_8_de_novembro
from .tela import Tela, TelaNaoMostrouError

ENDERECO = {
    "Identificação": "Casa",
    "CEP": "06454000",
    "Rua": "Alameda Rio Negro",
    "Número": "500",
    "Complemento": "Apto 42",
    "Bairro": "Alphaville",
    # Sem acento de propósito: `adb shell input text` não digita acento, e
    # um endereço em Barueri não precisa de nenhum.
    "Cidade": "Barueri",
    "UF": "SP",
}


@dataclass
class Roteiro:
    tela: Tela
    backend: Backend
    gabarito: list[Questao]
    acertar: set[int]
    pausa_segundos: float = 2.0
    log: Callable[[str], None] = print
    email_ana: str = field(default_factory=lambda: email_da_ana(datetime.now()))
    pedido_curto: str = ""

    def pausa(self, fator: float = 1.0) -> None:
        time.sleep(self.pausa_segundos * fator)

    # ── navegação comum ───────────────────────────────────────────────

    def ir_para_login(self) -> None:
        """Sai da conta que estiver na tela, de onde quer que o app esteja.

        Tela de staff tem "Sair" no topo; tela de aluno sai pelo perfil. Uma
        tela interna (pedido, mapa, notificações) volta até achar uma das
        duas. Deixa as cenas independentes de onde a anterior terminou.
        """
        t = self.tela
        for _ in range(8):
            t.garantir_app_em_foco()
            if t.achar("Insira suas credenciais"):
                return
            sair = t.achar("Sair", exato=True, clicavel=True)
            if sair:
                t.tocar_xy(*sair.centro)
                t.esperar("Insira suas credenciais", prazo=20)
                return
            if t.achar("Meu perfil", exato=True):
                t.rolar_ate("Sair", exato=True)
                t.tocar("Sair", exato=True, clicavel=True)
                t.esperar("Insira suas credenciais", prazo=20)
                return
            if t.achar("Voltar", exato=True, clicavel=True):
                t.voltar()
                time.sleep(1.2)
                continue
            aba_home = t.achar("Home", clicavel=True)
            if aba_home:
                # Numa aba raiz, voltar fecharia o app. A home e a loja têm o
                # perfil no ícone da esquerda; as demais abas não — nelas,
                # vai para a Home e tenta de novo.
                try:
                    t.tocar_icone("esquerda")
                    t.esperar("Meu perfil", prazo=8)
                    continue
                except TelaNaoMostrouError:
                    t.tocar_xy(*aba_home.centro)
                    time.sleep(2)
                    continue
            t.voltar()
            time.sleep(1.2)
        raise TelaNaoMostrouError("não consegui voltar para a tela de login")

    def abrir_notificacoes(self) -> None:
        """Toca o sino do topo. Sem não lidas ele se chama "Notificações";
        com não lidas, a acessibilidade anuncia só a contagem ("4")."""
        t = self.tela
        for _ in range(20):
            elementos = t.elementos()
            meio = max((e.limites[2] for e in elementos), default=0) // 2
            sinos = [
                e
                for e in elementos
                if e.clicavel
                and e.classe == "Button"
                and e.limites[1] < 300
                and e.centro[0] > meio
                and (e.texto == "Notificações" or e.texto.isdigit())
            ]
            if sinos:
                t.tocar_xy(*max(sinos, key=lambda e: e.limites[2]).centro)
                return
            time.sleep(0.5)
        raise TelaNaoMostrouError("o sino de notificações não apareceu no topo")

    def entrar_pelo_atalho(self, papel: str, marco: str) -> None:
        self.tela.tocar(f"({papel})", clicavel=True)
        self.tela.esperar(marco, prazo=30)

    def abrir_pedido(self) -> None:
        self.tela.tocar(f"Pedido #{self.pedido_curto}", prazo=30)


# ── preparo na tela (antes de gravar) ─────────────────────────────────


def salvar_atalhos_de_staff(r: Roteiro, senha: str) -> None:
    """Entra uma vez com cada conta de staff para o app guardar o atalho."""
    for email, marco in CONTAS_STAFF.items():
        r.tela.esperar("Insira suas credenciais", prazo=30)
        r.tela.preencher_campo("E-mail", email)
        r.tela.preencher_campo("Senha", senha)
        r.tela.tocar("Entrar", exato=True, clicavel=True)
        r.tela.esperar(marco, prazo=30)
        r.log(f"  atalho salvo: {email}")
        r.ir_para_login()


# ── roteiro gravado ───────────────────────────────────────────────────


def cadastro(r: Roteiro, senha: str) -> None:
    t = r.tela
    t.tocar("Cadastro", clicavel=True)
    t.esperar("Crie sua conta")
    r.pausa()
    t.preencher_campo("Nome", "Ana Souza")
    t.preencher_campo("E-mail", r.email_ana)
    t.preencher_campo("Telefone", "11987654321")

    rotulo = t.rolar_ate("Data de nascimento", exato=True)
    t.tocar_xy(540, rotulo.limites[3] + 80)
    t.tocar("Mudar para modo de entrada", exato=True)
    t.preencher(t.campos()[0], "15/03/2008")
    t.tocar("OK", exato=True)

    t.tocar("Selecione", exato=True)
    t.tocar("3º ano", exato=True)
    t.preencher_campo("Senha", senha)
    t.preencher_campo("Confirmar senha", senha)
    r.pausa(0.5)
    t.tocar("Cadastrar", exato=True, clicavel=True)
    t.esperar("Qual é o seu objetivo?", prazo=30)


def onboarding(r: Roteiro, hoje: date) -> None:
    t = r.tela
    r.pausa()
    t.preencher(t.campos()[0], "Medicina pelo ENEM")
    t.fechar_teclado()
    t.tocar("Data-alvo")
    t.tocar("Mudar para modo de entrada", exato=True)
    t.preencher(t.campos()[0], f"{proximo_8_de_novembro(hoje):%d/%m/%Y}")
    t.tocar("OK", exato=True)
    r.pausa()
    t.tocar("Começar", exato=True, clicavel=True)
    t.esperar("Percurso", prazo=30)
    r.pausa(1.5)  # o aviso "Seu percurso tem N etapas" aparece aqui


def roadmap(r: Roteiro) -> None:
    t = r.tela
    t.tocar("Estudo", clicavel=True)
    t.esperar("concluídas", prazo=30)
    r.pausa()
    for _ in range(2):
        t.rolar(700, duracao_ms=900)
        r.pausa(0.7)


def questionario(r: Roteiro) -> None:
    t = r.tela
    t.tocar("Quiz", clicavel=True)
    t.esperar("Escolha uma matéria")
    r.pausa(0.7)
    t.tocar("Biologia", exato=True)
    t.esperar("Temas de Biologia")
    r.pausa(0.7)
    t.tocar("Genética Básica", exato=True)
    t.esperar("Questão 1/", prazo=30)
    r.pausa(0.7)

    for _ in range(30):
        t.rolar_para_cima()
        time.sleep(0.6)
        elementos = t.elementos()
        enunciado = max(
            (
                e.texto
                for e in elementos
                if not e.clicavel and len(e.texto) > 40 and e.texto[1:2] != "\n"
            ),
            key=len,
        )
        letra = escolher_alternativa(enunciado, r.gabarito, r.acertar)

        alternativa = None
        for _ in range(4):
            alternativa = t.achar(f"{letra}\n", clicavel=True)
            if alternativa and alternativa.texto.startswith(f"{letra}\n"):
                break
            t.rolar(500)
            time.sleep(0.6)
        if alternativa is None:
            raise TelaNaoMostrouError(f"alternativa {letra} não apareceu")
        t.tocar_xy(*alternativa.centro)
        time.sleep(0.5)

        botao = None
        for _ in range(4):
            botao = t.achar("Avançar", exato=True) or t.achar("Finalizar", exato=True)
            if botao:
                break
            t.rolar(500)
            time.sleep(0.6)
        if botao is None:
            raise TelaNaoMostrouError("nem Avançar nem Finalizar apareceram")
        t.tocar_xy(*botao.centro)
        if botao.texto == "Finalizar":
            break
        time.sleep(0.8)

    t.esperar("QUESTIONÁRIO CONCLUÍDO", prazo=90)


def relatorio(r: Roteiro) -> None:
    t = r.tela
    r.pausa(1.5)
    t.rolar_ate("Desempenho por subtema")
    r.pausa()
    t.rolar_ate("Mensagem do seu tutor IA")
    t.rolar(500, duracao_ms=900)
    r.pausa(1.5)
    t.rolar_ate("Recomendações de estudo")
    t.rolar(700, duracao_ms=900)
    r.pausa(1.5)


def loja_e_compra(r: Roteiro) -> None:
    t = r.tela
    t.rolar_para_cima()
    t.tocar("Loja", clicavel=True)
    t.esperar("Parceiros", prazo=30)
    t.esperar("Leroy Merlin")
    r.pausa(1.5)

    t.preencher(t.campos()[0], "Mesa")
    t.fechar_teclado()
    t.rolar_ate("Mesa de estudo 120 cm")
    t.tocar("Mesa de estudo 120 cm")
    t.esperar("Adicionar ao carrinho")
    r.pausa()
    t.tocar("Adicionar ao carrinho", exato=True)
    time.sleep(1.5)
    t.tocar_icone("direita")
    t.esperar("Revisão do Carrinho")
    r.pausa()

    t.tocar("Sem endereço cadastrado")
    t.esperar("Novo endereço")
    for rotulo, valor in ENDERECO.items():
        t.preencher_campo(rotulo, valor)
    t.tocar("Salvar endereço", exato=True)
    t.esperar("Revisão do Carrinho", prazo=20)

    t.rolar_ate("Sem método de pagamento")
    t.tocar("Sem método de pagamento")
    t.esperar("Adicionar Método")
    t.tocar("PIX", exato=True)
    t.tocar("Salvar método", exato=True)
    t.esperar("Revisão do Carrinho", prazo=20)
    r.pausa(0.7)

    t.tocar("Finalizar Pedido", exato=True, clicavel=True)
    t.esperar("Confirmar pedido")
    r.pausa()
    t.tocar("Confirmar", exato=True)
    t.esperar("Pague com PIX", prazo=30)
    r.pausa(1.5)
    t.tocar("Concluir", exato=True)

    token = r.backend.entrar(r.email_ana)
    pedidos = r.backend.pedir("GET", "/orders", token)
    r.pedido_curto = pedidos[0]["id"][:8].upper()
    r.log(f"  pedido #{r.pedido_curto}")


def separador_reporta_falta(r: Roteiro) -> None:
    t = r.tela
    r.ir_para_login()
    r.entrar_pelo_atalho("separador", "Fila de Separação")
    r.pausa()
    r.abrir_pedido()
    t.tocar("Iniciar Separação", exato=True)
    t.esperar("Reportar falta de estoque")
    r.pausa()
    t.tocar("Reportar falta de estoque", exato=True)
    t.esperar("O aluno será notificado")
    t.preencher(t.campos()[0], "Sem estoque na prateleira")
    t.fechar_teclado()
    t.tocar("Reportar", exato=True)
    t.esperar("aguardando decisão do aluno", prazo=30)
    if t.notificacao_chegou("item em falta"):
        t.mostrar_gaveta(r.pausa_segundos + 3)
    else:
        r.log("  aviso: o push da Ana não chegou em 40s")


def aluna_escolhe_substituto(r: Roteiro) -> None:
    t = r.tela
    r.ir_para_login()
    r.entrar_pelo_atalho("aluno", "Percurso")
    r.abrir_notificacoes()
    t.tocar("item em falta", prazo=30)
    t.esperar("Resolver Pendência")
    r.pausa(1.5)
    t.tocar("Mesa de estudo compacta 90 cm")
    r.pausa(0.5)
    t.tocar("Confirmar substituição", exato=True)
    t.esperar("Notificações", prazo=20)
    r.pausa(0.5)


def separador_finaliza(r: Roteiro) -> None:
    t = r.tela
    r.ir_para_login()
    r.entrar_pelo_atalho("separador", "Fila de Separação")
    r.abrir_pedido()
    t.tocar("Mesa de estudo compacta 90 cm")
    r.pausa()
    t.tocar("Finalizar Separação", exato=True)
    t.esperar("Fila de Separação", prazo=20)
    r.pausa(0.5)


def entregador_coleta(r: Roteiro) -> None:
    t = r.tela
    r.ir_para_login()
    r.entrar_pelo_atalho("entregador", "Fila de Coleta")
    r.abrir_pedido()
    t.esperar("Confirmar Coleta")
    r.pausa()
    t.tocar("Confirmar Coleta", exato=True)
    t.esperar("Fila de Coleta", prazo=20)
    r.pausa(0.5)


def aluna_acompanha(r: Roteiro, segundos_de_mapa: float = 20) -> None:
    t = r.tela
    r.ir_para_login()
    r.entrar_pelo_atalho("aluno", "Percurso")
    t.tocar("Loja", clicavel=True)
    t.tocar("Meus Pedid", clicavel=True)
    t.esperar(f"Pedido #{r.pedido_curto}", prazo=20)
    r.pausa(0.7)
    t.tocar("Rastrear pedido", exato=True)
    t.esperar("Saiu para entrega", prazo=30)
    r.pausa(1.5)
    t.rolar_ate("Ver mapa", exato=True)
    t.tocar("Ver mapa", exato=True)
    t.esperar("Rota da Entrega", prazo=30)
    time.sleep(segundos_de_mapa)


def entregador_entrega(r: Roteiro) -> None:
    t = r.tela
    r.ir_para_login()
    r.entrar_pelo_atalho("entregador", "Fila de Coleta")
    t.tocar("Em rota", exato=True, clicavel=True)
    t.esperar(f"Pedido #{r.pedido_curto}", prazo=20)
    r.pausa()
    # A lista de "Entregas em Rota" já traz o botão no card do pedido.
    t.tocar("Entregue", exato=True, clicavel=True)
    t.esperar("Confirmar entrega?")
    t.tocar("Confirmar", exato=True, clicavel=True)
    t.esperar("não tem entregas em rota", prazo=20)
    if t.notificacao_chegou("entregue"):
        t.mostrar_gaveta(r.pausa_segundos + 2)


def painel_admin(r: Roteiro) -> None:
    t = r.tela
    r.ir_para_login()
    r.entrar_pelo_atalho("admin", "Painel Administrativo")
    t.esperar("RELATÓRIO EXECUTIVO", prazo=60)
    r.pausa(2)
    t.rolar(800, duracao_ms=900)
    r.pausa()
    t.tocar("Painel", exato=True, clicavel=True)
    r.pausa(2)
    t.rolar(800, duracao_ms=900)
    r.pausa()


CENAS_GRAVADAS = [
    "cadastro",
    "onboarding",
    "roadmap",
    "questionario",
    "relatorio",
    "loja_e_compra",
    "separador_reporta_falta",
    "aluna_escolhe_substituto",
    "separador_finaliza",
    "entregador_coleta",
    "aluna_acompanha",
    "entregador_entrega",
    "painel_admin",
]
