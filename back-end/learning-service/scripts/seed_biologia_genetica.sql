-- Questões de Genética Básica: quatro a mais para cada subtema do tema 3.
-- Roda direto no banco learning_db, DEPOIS de `seed_biologia_citologia.sql`.
--
-- Por que existe: a citologia criou "Leis de Mendel" (subtema 7) e "Herança
-- e Genótipo/Fenótipo" (subtema 8) com só duas questões cada. Um quiz de
-- Genética com quatro questões, todas fáceis ou médias, não aponta lacuna
-- nenhuma. Com seis por subtema, e níveis de 1 a 3 misturados, o relatório
-- tem o que mostrar. Os gabaritos também foram distribuídos: somadas às
-- quatro da citologia, as doze questões do tema têm três de cada letra.
--
-- IMPORTANTE: como as da citologia, as questões abaixo são ORIGINAIS, no
-- estilo do ENEM, escritas para teste/demo — não reproduzem itens do INEP.
-- Mesmo formato: quatro alternativas (A-D) em JSONB, gabarito de uma letra,
-- `fonte` 'Original (estilo ENEM)' e `ano` NULL.
--
-- DEPENDÊNCIA: materia 1, tema 3 e subtemas 7 e 8 vêm da citologia. Este
-- arquivo não os recria (seriam duas fontes para o mesmo registro). Rodado
-- antes dela, falha alto na chave estrangeira, em vez de gravar pela metade.
--
-- FAIXA DE ID: questões 1000-1007. A citologia ocupa 1-38 (ver o topo de
-- `seed_enem.sql`), e a API e `scripts/ingest_enem.py` gravam pela sequence
-- a partir dali — uma faixa colada em 38 colidiria com a primeira questão
-- que alguém tivesse cadastrado, e o `ON CONFLICT DO NOTHING` perderia a do
-- seed em silêncio.
--
-- Idempotente: `ON CONFLICT (id) DO NOTHING`, e o `setval` do fim reposiciona
-- a sequence para que a próxima inserção pela API não caia nesta faixa.

INSERT INTO questao (id, subtema_id, enunciado, alternativas, gabarito, nivel_dificuldade, fonte, ano) VALUES

-- ── Subtema 7: Leis de Mendel ────────────────────────────────────────

(1000, 7,
 'De acordo com a Primeira Lei de Mendel, cada gameta produzido por um indivíduo heterozigoto Aa recebe:',
 '{"A": "Sempre o alelo dominante A, que prevalece durante a meiose.", "B": "Os dois alelos do par, A e a.", "C": "Nenhum alelo, já que os gametas não carregam material genético.", "D": "Apenas um alelo do par, A ou a, com a mesma probabilidade."}',
 'D', 1, 'Original (estilo ENEM)', NULL),

(1001, 7,
 'Mendel cruzou plantas puras de ervilha de flores púrpuras com plantas puras de flores brancas e obteve, na geração F1, apenas plantas de flores púrpuras. Com a autofecundação das plantas F1, surgiram 800 plantas na geração F2. O número esperado de plantas de flores púrpuras na F2 é, aproximadamente:',
 '{"A": "200.", "B": "400.", "C": "600.", "D": "800."}',
 'C', 2, 'Original (estilo ENEM)', NULL),

(1002, 7,
 'Em ervilhas, a cor amarela da semente (V) é dominante sobre a cor verde (v). Um agricultor possui uma planta de sementes amarelas e quer saber se ela é homozigota ou heterozigota. O cruzamento mais indicado e o resultado que confirmaria a heterozigose são, respectivamente:',
 '{"A": "Cruzá-la com uma planta de sementes verdes (vv) e obter sementes amarelas e verdes em proporção próxima de 1:1.", "B": "Cruzá-la com uma planta de sementes verdes (vv) e obter apenas sementes amarelas.", "C": "Cruzá-la com outra planta de sementes amarelas e obter apenas sementes amarelas.", "D": "Autofecundá-la e obter apenas sementes verdes."}',
 'A', 2, 'Original (estilo ENEM)', NULL),

(1003, 7,
 'Em ervilhas, a cor amarela da semente (V) é dominante sobre a verde (v). Do cruzamento entre duas plantas heterozigotas (Vv x Vv), foram separadas apenas as sementes amarelas. Escolhendo-se ao acaso uma dessas sementes amarelas, a probabilidade de ela ser heterozigota é de:',
 '{"A": "1/4.", "B": "1/2.", "C": "2/3.", "D": "3/4."}',
 'C', 3, 'Original (estilo ENEM)', NULL),

-- ── Subtema 8: Herança e Genótipo/Fenótipo ───────────────────────────

(1004, 8,
 'Um indivíduo que possui dois alelos idênticos para um mesmo gene, como AA ou aa, é classificado como:',
 '{"A": "Heterozigoto.", "B": "Hemizigoto.", "C": "Poliploide.", "D": "Homozigoto."}',
 'D', 1, 'Original (estilo ENEM)', NULL),

(1005, 8,
 'Duas mudas de hortênsia obtidas por clonagem, e portanto geneticamente idênticas, foram cultivadas em solos diferentes. A que cresceu em solo ácido deu flores azuis, e a que cresceu em solo alcalino deu flores rosadas. Esse resultado evidencia que:',
 '{"A": "O fenótipo resulta da interação entre o genótipo e o ambiente.", "B": "O solo alterou o genótipo de uma das plantas.", "C": "A cor da flor é determinada apenas pelo ambiente, sem participação dos genes.", "D": "As duas plantas passaram a ter cariótipos diferentes."}',
 'A', 2, 'Original (estilo ENEM)', NULL),

(1006, 8,
 'Em cobaias, a pelagem preta (B) é dominante sobre a branca (b). Observando apenas a cor da pelagem de um grupo de animais, é possível afirmar com certeza o genótipo:',
 '{"A": "Dos animais pretos, que são todos BB.", "B": "De todos os animais, pois fenótipo e genótipo sempre coincidem.", "C": "Dos animais brancos, que são necessariamente bb.", "D": "De nenhum animal, pois a cor da pelagem não é hereditária."}',
 'C', 2, 'Original (estilo ENEM)', NULL),

(1007, 8,
 'Um casal em que ambos apresentam determinada característica teve uma filha que não a apresenta. Considerando que a característica é condicionada por um gene autossômico com dominância completa, conclui-se que:',
 '{"A": "A característica é recessiva e os pais são homozigotos.", "B": "A característica é recessiva e a filha é heterozigota.", "C": "A característica é dominante e a filha é homozigota dominante.", "D": "A característica é dominante e os dois pais são heterozigotos."}',
 'D', 3, 'Original (estilo ENEM)', NULL)

ON CONFLICT (id) DO NOTHING;

-- Mesma correção de sequence dos outros seeds, para que próximos INSERTs
-- feitos pela API (ex: ingest_enem.py) não colidam com estes ids.
SELECT setval('questao_id_seq', (SELECT MAX(id) FROM questao));
