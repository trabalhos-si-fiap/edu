import unittest

from demo_roteiro.preparo import ContasFaltandoError, garantir_contas

CONTAS = ["admin@demo.edu", "separador@demo.edu", "entregador@demo.edu"]


class GarantirContasTest(unittest.TestCase):
    def test_todas_existem_nao_semeia(self):
        semeou = []

        resultado = garantir_contas(
            CONTAS, entrar=lambda email: True, semear=lambda: semeou.append(1)
        )

        self.assertEqual(semeou, [])
        self.assertEqual(resultado.existentes, CONTAS)
        self.assertEqual(resultado.criadas, [])

    def test_falta_alguma_semeia_uma_vez_e_confere_de_novo(self):
        existentes = {"admin@demo.edu"}
        semeou = []

        def semear():
            semeou.append(1)
            existentes.update(CONTAS)

        resultado = garantir_contas(CONTAS, entrar=lambda email: email in existentes, semear=semear)

        self.assertEqual(semeou, [1])
        self.assertEqual(resultado.existentes, ["admin@demo.edu"])
        self.assertEqual(resultado.criadas, ["separador@demo.edu", "entregador@demo.edu"])

    def test_seed_nao_resolve_levanta_com_as_que_faltam(self):
        with self.assertRaises(ContasFaltandoError) as ctx:
            garantir_contas(
                CONTAS,
                entrar=lambda email: email == "admin@demo.edu",
                semear=lambda: None,
            )

        self.assertEqual(ctx.exception.faltando, ["separador@demo.edu", "entregador@demo.edu"])


if __name__ == "__main__":
    unittest.main()
