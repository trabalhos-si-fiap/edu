import unittest

from demo_roteiro.tela import Elemento, achar_em, escapar_texto, ler_elementos


def _no(classe, bounds, texto="", desc="", pacote="br.com.fiap.estuda_app", **extra):
    atributos = {"clickable": "false", "scrollable": "false", **extra}
    resto = " ".join(f'{k}="{v}"' for k, v in atributos.items())
    return (
        f'<node index="0" text="{texto}" resource-id="" class="{classe}" package="{pacote}"'
        f' content-desc="{desc}" {resto} bounds="{bounds}" hint=""'
    )


# Recorte do app no celular: o Flutter publica o texto visível em
# `content-desc` (não em `text`) e escapa quebra de linha. O "Avançar" está
# meio escondido embaixo da área rolável e o "Finalizar" inteiro fora dela.
XML = f"""<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
{_no("android.widget.FrameLayout", "[0,0][1080,2256]")}>
{_no("android.view.View", "[247,345][833,573]", desc="Bem vindo(a)&#10;de volta!")} />
{_no("android.widget.EditText", "[120,969][960,1137]", texto="separador@demo.edu", clickable="true")} />
{_no("android.widget.ScrollView", "[0,256][1080,2082]", scrollable="true")}>
{_no("android.widget.Button", "[558,2000][1020,2156]", desc="Avançar", clickable="true")} />
{_no("android.widget.Button", "[558,2200][1020,2372]", desc="Finalizar", clickable="true")} />
</node>
</node>
{_no("android.widget.Button", "[0,2256][360,2400]", desc="Voltar", pacote="com.android.systemui", clickable="true")} />
</hierarchy>"""


def _por_texto(texto, pacote=None):
    return next(e for e in ler_elementos(XML, pacote) if e.texto == texto)


class LerElementosTest(unittest.TestCase):
    def test_le_texto_de_content_desc_e_de_text(self):
        textos = [e.texto for e in ler_elementos(XML)]
        self.assertIn("Bem vindo(a)\nde volta!", textos)
        self.assertIn("separador@demo.edu", textos)

    def test_le_classe_curta_clicavel_rolavel_e_limites(self):
        campo = _por_texto("separador@demo.edu")
        self.assertEqual(campo.classe, "EditText")
        self.assertTrue(campo.clicavel)
        self.assertEqual(campo.limites, (120, 969, 960, 1137))
        self.assertTrue(next(e for e in ler_elementos(XML) if e.classe == "ScrollView").rolavel)

    def test_centro_e_o_meio_dos_limites(self):
        self.assertEqual(
            Elemento("x", "View", False, False, (100, 200, 300, 400)).centro, (200, 300)
        )

    def test_xml_vazio_nao_tem_elementos(self):
        self.assertEqual(ler_elementos(""), [])

    def test_limites_sao_cortados_pela_area_do_pai(self):
        # O uiautomator2 devolve o retângulo inteiro do botão; tocar no centro
        # dele caía na barra de navegação do Android, fora do app.
        self.assertEqual(_por_texto("Avançar").limites, (558, 2000, 1020, 2082))

    def test_elemento_fora_da_area_do_pai_nao_aparece(self):
        self.assertNotIn("Finalizar", [e.texto for e in ler_elementos(XML)])

    def test_sem_pacote_le_todas_as_janelas(self):
        self.assertEqual(ler_elementos(XML)[-1].texto, "Voltar")

    def test_com_pacote_ignora_barra_do_sistema_e_teclado(self):
        # O uiautomator2 lê todas as janelas da tela; o "Voltar" da barra de
        # navegação não pode ser confundido com o botão Voltar do app.
        textos = [e.texto for e in ler_elementos(XML, pacote="br.com.fiap.estuda_app")]
        self.assertEqual(len(textos), 5)
        self.assertNotIn("Voltar", textos)


ELEMENTOS = (
    Elemento("Pedido #01A0A0DC", "View", False, False, (0, 0, 10, 10)),
    Elemento("Sair", "Button", True, False, (0, 10, 10, 20)),
    Elemento("Sair da conta", "Button", True, False, (0, 20, 10, 30)),
    Elemento("sair", "View", False, False, (0, 30, 10, 40)),
)


class AcharEmTest(unittest.TestCase):
    def test_trecho_ignora_maiusculas(self):
        self.assertEqual(achar_em(ELEMENTOS, "pedido #01a").texto, "Pedido #01A0A0DC")

    def test_exato_exige_o_texto_inteiro(self):
        self.assertEqual(achar_em(ELEMENTOS, "Sair", exato=True).limites, (0, 10, 10, 20))
        self.assertIsNone(achar_em(ELEMENTOS, "Sai", exato=True))

    def test_filtra_por_clicavel(self):
        self.assertEqual(achar_em(ELEMENTOS, "sair", clicavel=False).classe, "View")

    def test_indice_escolhe_entre_os_achados(self):
        self.assertEqual(achar_em(ELEMENTOS, "sair", indice=1).texto, "Sair da conta")
        self.assertIsNone(achar_em(ELEMENTOS, "sair", indice=3))


class EscaparTextoTest(unittest.TestCase):
    def test_espaco_vira_percent_s(self):
        self.assertEqual(escapar_texto("Medicina pelo ENEM"), "Medicina%spelo%sENEM")

    def test_caractere_de_shell_fica_entre_aspas(self):
        self.assertEqual(escapar_texto("Ana@Demo(1)&"), "'Ana@Demo(1)&'")

    def test_aspas_simples_sao_escapadas(self):
        self.assertEqual(escapar_texto("d'agua"), "'d'\"'\"'agua'")

    def test_recusa_texto_fora_de_ascii(self):
        # `adb shell input text` não digita acento; melhor falhar alto do que
        # digitar "Sao" calado no lugar de "São".
        with self.assertRaises(ValueError):
            escapar_texto("São Paulo")


if __name__ == "__main__":
    unittest.main()
