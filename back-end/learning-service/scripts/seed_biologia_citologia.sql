-- Seed de conteúdo para testar o fluxo de diagnóstico ponta a ponta.
-- Roda direto no banco learning_db.
--
-- IMPORTANTE: as questões abaixo são ORIGINAIS, escritas no estilo do
-- ENEM para fins de teste/demo — não são reproduções de itens reais do
-- INEP (evita qualquer questão de direito autoral). Para produção, usar
-- `scripts/ingest_enem.py` (api.enem.dev) ou material curado pela equipe.
--
-- Estrutura criada:
--   Biologia
--     1. Introdução ao Estudo da Célula   (pré-requisito de Citologia)
--     2. Citologia                         (tema principal do fluxo)
--     3. Genética Básica                   (próximo tema após Citologia)

INSERT INTO materia (id, nome) VALUES
(1, 'Biologia')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tema (id, materia_id, nome, ordem) VALUES
(1, 1, 'Introdução ao Estudo da Célula', 1),
(2, 1, 'Citologia', 2),
(3, 1, 'Genética Básica', 3)
ON CONFLICT (id) DO NOTHING;

INSERT INTO subtema (id, tema_id, nome, ordem, videoaula_base_url, videoaula_revisao_url, descricao_ia) VALUES
(1, 1, 'Teoria Celular e Tipos de Célula', 1,
    'https://www.youtube.com/results?search_query=teoria+celular+tipos+de+c%C3%A9lula+aula',
    'https://www.youtube.com/results?search_query=teoria+celular+resumo+revis%C3%A3o',
    'teoria celular, célula procarionte, célula eucarionte, origem das células, Schleiden, Schwann, todos os seres vivos são formados por células'),
(2, 1, 'Microscopia e Métodos de Estudo', 2,
    'https://www.youtube.com/results?search_query=microscopia+%C3%B3ptica+e+eletr%C3%B4nica+aula',
    'https://www.youtube.com/results?search_query=microscopia+resumo+revis%C3%A3o',
    'microscópio óptico, microscópio eletrônico, resolução, ampliação, técnicas de observação celular'),

(3, 2, 'Membrana Plasmática', 1,
    'https://www.youtube.com/results?search_query=membrana+plasm%C3%A1tica+transporte+aula',
    'https://www.youtube.com/results?search_query=membrana+plasm%C3%A1tica+resumo+revis%C3%A3o',
    'membrana plasmática, mosaico fluido, fosfolipídios, bicamada lipídica, transporte de substâncias, osmose, difusão, transporte ativo, bomba de sódio e potássio, permeabilidade seletiva, endocitose, exocitose, fagocitose, pinocitose, hipertônico, hipotônico, isotônico, crenação, plasmólise'),
(4, 2, 'Organelas Citoplasmáticas', 2,
    'https://www.youtube.com/results?search_query=organelas+citoplasm%C3%A1ticas+aula',
    'https://www.youtube.com/results?search_query=organelas+citoplasm%C3%A1ticas+resumo+revis%C3%A3o',
    'organelas citoplasmáticas, lisossomo, digestão intracelular, retículo endoplasmático liso, retículo endoplasmático rugoso, complexo de Golgi, ribossomo, síntese de proteínas, vacúolo, peroxissomo, secreção celular'),
(5, 2, 'Metabolismo Energético', 3,
    'https://www.youtube.com/results?search_query=mitoc%C3%B4ndria+cloroplasto+respira%C3%A7%C3%A3o+celular+aula',
    'https://www.youtube.com/results?search_query=respira%C3%A7%C3%A3o+celular+fotoss%C3%ADntese+resumo',
    'mitocôndria, respiração celular, ATP, cloroplasto, fotossíntese, glicólise, ciclo de Krebs, cadeia respiratória, teoria endossimbiótica, energia química, metabolismo energético da célula'),
(6, 2, 'Núcleo e Divisão Celular', 4,
    'https://www.youtube.com/results?search_query=n%C3%BAcleo+celular+mitose+meiose+aula',
    'https://www.youtube.com/results?search_query=mitose+meiose+resumo+revis%C3%A3o',
    'núcleo celular, envoltório nuclear, cromatina, cromossomos, mitose, meiose, prófase, metáfase, anáfase, telófase, divisão celular, ciclo celular, gametas, células somáticas'),

(7, 3, 'Leis de Mendel', 1,
    'https://www.youtube.com/results?search_query=primeira+lei+de+mendel+aula',
    'https://www.youtube.com/results?search_query=leis+de+mendel+resumo+revis%C3%A3o',
    'leis de Mendel, primeira lei, lei da segregação, alelos, cruzamento, proporção genotípica, proporção fenotípica, ervilhas, hereditariedade'),
(8, 3, 'Herança e Genótipo/Fenótipo', 2,
    'https://www.youtube.com/results?search_query=genótipo+fenótipo+heran%C3%A7a+gen%C3%A9tica+aula',
    'https://www.youtube.com/results?search_query=gen%C3%B3tipo+fen%C3%B3tipo+resumo+revis%C3%A3o',
    'genótipo, fenótipo, homozigoto, heterozigoto, dominância completa, herança genética, alelo dominante, alelo recessivo, cariótipo')
ON CONFLICT (id) DO NOTHING;

-- ── Tema 1: Introdução ao Estudo da Célula ──────────────────────────

INSERT INTO questao (id, subtema_id, enunciado, alternativas, gabarito, nivel_dificuldade, fonte, ano) VALUES
(1, 1,
 'A teoria celular estabelece que todos os seres vivos são formados por células e que estas se originam de outras células preexistentes. Com base nesse princípio, é correto afirmar que:',
 '{"A": "Novas células surgem espontaneamente a partir de matéria não viva.", "B": "Toda célula se origina da divisão de uma célula preexistente.", "C": "Apenas os seres multicelulares possuem células verdadeiras.", "D": "Vírus são considerados células simples, pois contêm material genético."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(2, 1,
 'Diferentemente das células eucarióticas, as células procarióticas se caracterizam por:',
 '{"A": "Possuir núcleo delimitado por membrana.", "B": "Apresentar organelas membranosas complexas, como mitocôndrias.", "C": "Não possuir envoltório nuclear, com o material genético disperso no citoplasma.", "D": "Serem exclusivas de organismos multicelulares."}',
 'C', 2, 'Original (estilo ENEM)', NULL),

(3, 2,
 'O microscópio eletrônico permite observar estruturas muito menores do que o microscópio óptico principalmente porque:',
 '{"A": "Utiliza uma fonte de luz mais intensa.", "B": "Usa feixes de elétrons, que possuem comprimento de onda muito menor que o da luz visível.", "C": "Amplia a imagem por meio de lentes de vidro mais espessas.", "D": "Permite observar células vivas em movimento."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(4, 2,
 'Para observar organelas internas de uma célula com grande nível de detalhe, o pesquisador deve preferencialmente utilizar:',
 '{"A": "Microscópio óptico comum.", "B": "Lupa de mão.", "C": "Microscópio eletrônico de transmissão.", "D": "Olho nu com auxílio de corante."}',
 'C', 2, 'Original (estilo ENEM)', NULL),

-- ── Tema 2: Citologia (foco principal do fluxo) ─────────────────────

(5, 3,
 'O modelo do mosaico fluido descreve a membrana plasmática como uma estrutura composta principalmente por:',
 '{"A": "Uma parede rígida de celulose.", "B": "Uma bicamada de fosfolipídios com proteínas inseridas, capaz de se movimentar lateralmente.", "C": "Um único tipo de proteína transportadora fixa.", "D": "Uma camada única de carboidratos."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(6, 3,
 'O transporte de água através da membrana plasmática, a favor do gradiente de concentração, sem gasto de energia, é chamado de:',
 '{"A": "Osmose.", "B": "Endocitose.", "C": "Transporte ativo.", "D": "Fagocitose."}',
 'A', 2, 'Original (estilo ENEM)', NULL),

(7, 3,
 'Em uma solução hipertônica em relação ao meio intracelular, uma célula animal tende a:',
 '{"A": "Incorporar água e aumentar de volume.", "B": "Perder água para o meio externo, podendo sofrer crenação.", "C": "Permanecer inalterada, pois a membrana é impermeável à água.", "D": "Realizar fagocitose para compensar a perda de íons."}',
 'B', 2, 'Original (estilo ENEM)', NULL),

(8, 3,
 'O transporte ativo de íons sódio e potássio através da bomba Na+/K+-ATPase ocorre:',
 '{"A": "A favor do gradiente de concentração de ambos os íons, sem consumo de ATP.", "B": "Contra o gradiente de concentração de ambos os íons, com consumo de ATP.", "C": "Apenas durante a divisão celular.", "D": "Exclusivamente em células vegetais."}',
 'B', 3, 'Original (estilo ENEM)', NULL),

(9, 3,
 'As proteínas de membrana que atuam como receptores específicos para hormônios e neurotransmissores são fundamentais para:',
 '{"A": "A rigidez estrutural da parede celular.", "B": "A comunicação celular e resposta a sinais externos.", "C": "A síntese de ATP na mitocôndria.", "D": "A duplicação do DNA durante a mitose."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(10, 4,
 'A organela responsável pela digestão intracelular de macromoléculas e organelas desgastadas, contendo enzimas hidrolíticas, é:',
 '{"A": "O complexo de Golgi.", "B": "O lisossomo.", "C": "O retículo endoplasmático liso.", "D": "O ribossomo."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(11, 4,
 'O retículo endoplasmático rugoso se diferencia do liso principalmente por:',
 '{"A": "Não possuir membrana.", "B": "Estar presente exclusivamente em células vegetais.", "C": "Apresentar ribossomos aderidos à sua superfície, atuando na síntese de proteínas.", "D": "Ser o local de armazenamento de amido."}',
 'C', 2, 'Original (estilo ENEM)', NULL),

(12, 4,
 'O complexo de Golgi tem como principal função:',
 '{"A": "Realizar a fotossíntese.", "B": "Modificar, empacotar e direcionar proteínas e lipídios para seus destinos finais na célula.", "C": "Produzir ATP a partir da glicose.", "D": "Armazenar o material genético da célula."}',
 'B', 2, 'Original (estilo ENEM)', NULL),

(13, 4,
 'Em células com alta atividade secretora, como as glandulares, espera-se encontrar uma maior quantidade de:',
 '{"A": "Retículo endoplasmático rugoso e complexo de Golgi bem desenvolvidos.", "B": "Vacúolos de reserva apenas.", "C": "Cloroplastos, para produção de energia luminosa.", "D": "Parede celular espessa de celulose."}',
 'A', 3, 'Original (estilo ENEM)', NULL),

(14, 4,
 'Os ribossomos, estruturas responsáveis pela síntese proteica, podem ser encontrados:',
 '{"A": "Apenas no núcleo celular.", "B": "Livres no citoplasma ou aderidos ao retículo endoplasmático rugoso.", "C": "Exclusivamente dentro das mitocôndrias.", "D": "Somente em células procarióticas."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(15, 5,
 'A mitocôndria é a organela responsável principalmente por:',
 '{"A": "Realizar a fotossíntese e produzir glicose.", "B": "Realizar a respiração celular, convertendo energia química em ATP.", "C": "Digerir partículas fagocitadas.", "D": "Sintetizar proteínas de secreção."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(16, 5,
 'Os cloroplastos, presentes em células vegetais e algas, são responsáveis por:',
 '{"A": "Converter energia luminosa em energia química, na forma de glicose, durante a fotossíntese.", "B": "Realizar a respiração celular anaeróbica.", "C": "Armazenar exclusivamente água e sais minerais.", "D": "Digerir macromoléculas complexas."}',
 'A', 2, 'Original (estilo ENEM)', NULL),

(17, 5,
 'Tanto mitocôndrias quanto cloroplastos possuem DNA próprio e ribossomos semelhantes aos de bactérias. Essa observação é uma das principais evidências que sustentam a:',
 '{"A": "Teoria da geração espontânea.", "B": "Teoria endossimbiótica, segundo a qual essas organelas se originaram de procariontes ancestrais.", "C": "Teoria da seleção natural aplicada às organelas.", "D": "Teoria celular clássica de Schleiden e Schwann."}',
 'B', 3, 'Original (estilo ENEM)', NULL),

(18, 5,
 'Durante a respiração celular aeróbica, a etapa que ocorre na matriz mitocondrial e produz CO2 e coenzimas reduzidas é:',
 '{"A": "A glicólise.", "B": "O ciclo de Krebs.", "C": "A fotólise da água.", "D": "A cadeia respiratória."}',
 'B', 2, 'Original (estilo ENEM)', NULL),

(19, 6,
 'O envoltório nuclear, que delimita o núcleo das células eucarióticas, é composto por:',
 '{"A": "Uma única membrana lipídica contínua.", "B": "Duas membranas com poros que permitem a troca de substâncias com o citoplasma.", "C": "Uma parede rígida de celulose.", "D": "Uma camada exclusiva de proteínas estruturais."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(20, 6,
 'Durante a mitose, a fase em que os cromossomos se alinham na região equatorial da célula é denominada:',
 '{"A": "Prófase.", "B": "Metáfase.", "C": "Anáfase.", "D": "Telófase."}',
 'B', 2, 'Original (estilo ENEM)', NULL),

(21, 6,
 'A principal função biológica da mitose em organismos multicelulares é:',
 '{"A": "Produzir gametas com metade do número de cromossomos.", "B": "Promover crescimento, reposição celular e reparo de tecidos, gerando células geneticamente idênticas.", "C": "Aumentar a variabilidade genética da espécie.", "D": "Reduzir o número de cromossomos pela metade."}',
 'B', 2, 'Original (estilo ENEM)', NULL),

(22, 6,
 'Diferentemente da mitose, a meiose se caracteriza por:',
 '{"A": "Gerar duas células-filhas idênticas à célula-mãe.", "B": "Envolver duas divisões celulares sucessivas, resultando em quatro células com metade do número de cromossomos.", "C": "Ocorrer exclusivamente em células somáticas.", "D": "Não envolver a duplicação do material genético."}',
 'B', 3, 'Original (estilo ENEM)', NULL),

-- ── Tema 3: Genética Básica ──────────────────────────────────────────

(23, 7,
 'A Primeira Lei de Mendel, também chamada de Lei da Segregação, estabelece que:',
 '{"A": "Genes localizados no mesmo cromossomo segregam sempre juntos.", "B": "Cada característica é determinada por um par de fatores (alelos) que se separam na formação dos gametas.", "C": "Todas as características são poligênicas.", "D": "Os alelos recessivos nunca se manifestam no fenótipo."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(24, 7,
 'No cruzamento entre dois indivíduos heterozigotos (Aa x Aa), a proporção genotípica esperada na prole é:',
 '{"A": "1 AA : 2 Aa : 1 aa.", "B": "1 AA : 1 aa apenas.", "C": "3 AA : 1 aa.", "D": "Todos os descendentes serão Aa."}',
 'A', 2, 'Original (estilo ENEM)', NULL),

(25, 8,
 'O conjunto de genes de um indivíduo, incluindo os alelos não expressos, é chamado de:',
 '{"A": "Fenótipo.", "B": "Genótipo.", "C": "Cariótipo.", "D": "Genoma somático."}',
 'B', 1, 'Original (estilo ENEM)', NULL),

(26, 8,
 'Em uma herança com dominância completa, um indivíduo heterozigoto (Aa) para uma característica apresentará fenótipo:',
 '{"A": "Intermediário entre os dois homozigotos.", "B": "Idêntico ao do homozigoto dominante (AA).", "C": "Idêntico ao do homozigoto recessivo (aa).", "D": "Sempre distinto de ambos os homozigotos."}',
 'B', 2, 'Original (estilo ENEM)', NULL)

ON CONFLICT (id) DO NOTHING;

-- Corrige as sequences após inserts com ID explícito, para que próximos
-- INSERTs feitos pela API (ex: ingest_enem.py) não colidam com estes.
SELECT setval('materia_id_seq', (SELECT MAX(id) FROM materia));
SELECT setval('tema_id_seq', (SELECT MAX(id) FROM tema));
SELECT setval('subtema_id_seq', (SELECT MAX(id) FROM subtema));
SELECT setval('questao_id_seq', (SELECT MAX(id) FROM questao));
