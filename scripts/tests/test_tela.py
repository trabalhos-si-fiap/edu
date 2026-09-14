import unittest

from demo_roteiro.tela import Elemento, achar_em, escapar_texto, ler_elementos

# Recorte real de `uiautomator dump` do app no celular: o Flutter publica o
# texto visível em `content-desc` (não em `text`) e escapa quebra de linha.
XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
<node index="0" text="" resource-id="" class="android.view.View" package="br.com.fiap.estuda_app"
 content-desc="Bem vindo(a)&#10;de volta!" checkable="false" checked="false" clickable="false"
 enabled="true" focusable="false" focused="false" scrollable="false" long-clickable="false"
 password="false" selected="false" bounds="[247,345][833,573]" hint="">
<node index="1" text="separador@demo.edu" resource-id="" class="android.widget.EditText"
 package="br.com.fiap.estuda_app" content-desc="" checkable="false" checked="false" clickable="true"
 enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false"
 password="false" selected="false" bounds="[120,969][960,1137]" hint="E-mail" />
<node index="2" text="" resource-id="" class="android.widget.ScrollView"
 package="br.com.fiap.estuda_app" content-desc="" checkable="false" checked="false"
 clickable="false" enabled="true" focusable="false" focused="false" scrollable="true" long-clickable="false" password="false" selected="false"
 bounds="[0,256][1080,2082]" hint="" />
</node>
<node index="0" text="" resource-id="" class="android.widget.Button" package="com.android.systemui"
 content-desc="Voltar" checkable="false" checked="false" clickable="true" enabled="true"
 focusable="true" focused="false" scrollable="false" long-clickable="false" password="false"
 selected="false" bounds="[0,2256][360,2400]" hint="" />
</hierarchy>"""


class LerElementosTest(unittest.TestCase):
    def test_le_texto_de_content_desc_e_de_text(self):
        elementos = ler_elementos(XML)
        self.assertEqual(elementos[0].texto, "Bem vindo(a)\nde volta!")
        self.assertEqual(elementos[1].texto, "separador@demo.edu")

    def test_le_classe_curta_clicavel_rolavel_e_limites(self):
        campo = ler_elementos(XML)[1]
        self.assertEqual(campo.classe, "EditText")
        self.assertTrue(campo.clicavel)
        self.assertEqual(campo.limites, (120, 969, 960, 1137))
        self.assertTrue(ler_elementos(XML)[2].rolavel)

    def test_centro_e_o_meio_dos_limites(self):
        self.assertEqual(
            Elemento("x", "View", False, False, (100, 200, 300, 400)).centro, (200, 300)
        )

    def test_xml_vazio_nao_tem_elementos(self):
        self.assertEqual(ler_elementos(""), [])

    def test_sem_pacote_le_todas_as_janelas(self):
        self.assertEqual(ler_elementos(XML)[-1].texto, "Voltar")

    def test_com_pacote_ignora_barra_do_sistema_e_teclado(self):
        # O uiautomator2 lê todas as janelas da tela; o "Voltar" da barra de
        # navegação não pode ser confundido com o botão Voltar do app.
        textos = [e.texto for e in ler_elementos(XML, pacote="br.com.fiap.estuda_app")]
        self.assertEqual(len(textos), 3)
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
