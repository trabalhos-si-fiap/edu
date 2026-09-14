import unittest

from demo_roteiro.tela import Elemento, escapar_texto, ler_elementos

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
