import unittest
from datetime import UTC, date, datetime

from demo_roteiro.roteiro_dados import (
    Questao,
    email_da_ana,
    escolher_alternativa,
    proximo_8_de_novembro,
    validar_senha,
)

GABARITO = [
    Questao(
        7,
        "B",
        "A Primeira Lei de Mendel, também chamada de Lei da Segregação, afirma que:",
    ),
    Questao(
        7,
        "A",
        "Em ervilhas, a cor amarela da semente (V) é dominante sobre a verde (v). Um agricultor possui uma planta de sementes amarelas e quer saber se ela é homozigota ou heterozigota.",
    ),
    Questao(
        7,
        "C",
        "Em ervilhas, a cor amarela da semente (V) é dominante sobre a verde (v). Do cruzamento Vv x Vv, escolhe-se ao acaso uma semente amarela.",
    ),
    Questao(
        8,
        "D",
        "Um indivíduo que possui dois alelos idênticos para um gene é chamado de:",
    ),
]


class ProximoOitoDeNovembroTest(unittest.TestCase):
    def test_antes_de_novembro_e_o_deste_ano(self):
        self.assertEqual(proximo_8_de_novembro(date(2026, 9, 14)), date(2026, 11, 8))

    def test_no_dia_ou_depois_e_o_do_ano_seguinte(self):
        # A data-alvo precisa estar no futuro; no próprio dia 8 já não está.
        self.assertEqual(proximo_8_de_novembro(date(2026, 11, 8)), date(2027, 11, 8))
        self.assertEqual(proximo_8_de_novembro(date(2026, 12, 1)), date(2027, 11, 8))


class EscolherAlternativaTest(unittest.TestCase):
    def test_acerta_nos_subtemas_pedidos(self):
        tela = (
            "Em ervilhas, a cor amarela da semente (V) é dominante sobre a verde (v). "
            "Do cruzamento Vv x Vv, escolhe-se ao acaso uma semente amarela. Qual a chance"
        )
        self.assertEqual(escolher_alternativa(tela, GABARITO, acertar={7}), "C")

    def test_distingue_enunciados_com_o_mesmo_comeco(self):
        tela = (
            "Em ervilhas, a cor amarela da semente (V) é dominante sobre a verde (v). "
            "Um agricultor possui uma planta de sementes amarelas"
        )
        self.assertEqual(escolher_alternativa(tela, GABARITO, acertar={7}), "A")

    def test_erra_de_proposito_fora_dos_subtemas_pedidos(self):
        tela = "Um indivíduo que possui dois alelos idênticos para um gene é chamado de:"
        escolha = escolher_alternativa(tela, GABARITO, acertar={7})
        self.assertNotEqual(escolha, "D")
        self.assertIn(escolha, "ABC")


class EmailDaAnaTest(unittest.TestCase):
    def test_e_unico_por_segundo(self):
        self.assertEqual(
            email_da_ana(datetime(2026, 9, 14, 9, 5, 7, tzinfo=UTC)),
            "ana.20260914090507@example.com",
        )


class ValidarSenhaTest(unittest.TestCase):
    def test_aceita_a_regra_do_cadastro(self):
        validar_senha("Exemplo@1234")

    def test_recusa_curta_ou_sem_especial(self):
        for senha in ("Ab@1", "SemEspecial123", ""):
            with self.subTest(senha=senha), self.assertRaises(ValueError):
                validar_senha(senha)

    def test_recusa_fora_de_ascii(self):
        with self.assertRaises(ValueError):
            validar_senha("Senhã@12345")


if __name__ == "__main__":
    unittest.main()
