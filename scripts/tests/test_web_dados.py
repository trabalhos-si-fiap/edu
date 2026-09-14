import unittest

from demo_web.dados import ler_tamanho, pedido_em_destaque, quantidade_de_reposicao


def _pedido(uuid, status, criado_em):
    return {"id": uuid, "status": status, "total": "279.90", "created_at": criado_em}


class PedidoEmDestaqueTest(unittest.TestCase):
    def test_escolhe_o_entregue_mais_recente(self):
        pedidos = [
            _pedido("01a0a113-aaaa", "AGUARDANDO_SUBSTITUICAO", "2026-09-14T15:00:00Z"),
            _pedido("01a0a119-bbbb", "ENTREGUE", "2026-09-14T15:04:00Z"),
            _pedido("01a0a1af-cccc", "ENTREGUE", "2026-09-14T17:48:00Z"),
        ]
        self.assertEqual(pedido_em_destaque(pedidos), "01A0A1AF")

    def test_nao_depende_da_ordem_da_lista(self):
        pedidos = [
            _pedido("01a0a1af-cccc", "ENTREGUE", "2026-09-14T17:48:00+00:00"),
            _pedido("01a0a119-bbbb", "ENTREGUE", "2026-09-14T15:04:00+00:00"),
        ]
        self.assertEqual(pedido_em_destaque(pedidos), "01A0A1AF")

    def test_sem_entregue_fica_com_o_mais_recente(self):
        # Rodar o painel antes da demo do celular terminar ainda mostra algo.
        pedidos = [
            _pedido("0000aaaa-1", "CRIADO", "2026-09-14T10:00:00Z"),
            _pedido("0000bbbb-2", "EM_TRANSITO", "2026-09-14T11:00:00Z"),
        ]
        self.assertEqual(pedido_em_destaque(pedidos), "0000BBBB")

    def test_sem_pedido_nenhum(self):
        self.assertIsNone(pedido_em_destaque([]))


class LerTamanhoTest(unittest.TestCase):
    def test_largura_por_altura(self):
        self.assertEqual(ler_tamanho("1920x1080"), (1920, 1080))
        self.assertEqual(ler_tamanho("1600X900"), (1600, 900))

    def test_recusa_formato_errado_ou_zero(self):
        for texto in ("1920", "1920x", "x1080", "0x1080", "1920x-1", "grande"):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                ler_tamanho(texto)


class QuantidadeDeReposicaoTest(unittest.TestCase):
    def test_repoe_bem_acima_do_minimo(self):
        self.assertEqual(quantidade_de_reposicao(15), 30)

    def test_minimo_baixo_ainda_repoe_um_lote(self):
        self.assertEqual(quantidade_de_reposicao(0), 20)
        self.assertEqual(quantidade_de_reposicao(5), 20)


if __name__ == "__main__":
    unittest.main()
