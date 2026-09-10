-- Estrutura do ENEM: matérias, temas e subtemas das quatro áreas.
--
-- SEED DE ESTRUTURA, não de conteúdo: nenhuma questão entra aqui. As
-- questões entram por matéria, em arquivos próprios, no formato de
-- `seed_biologia_citologia.sql` — e o roadmap funciona com qualquer
-- quantidade delas: subtema sem questão aparece no percurso marcado como
-- indisponível para praticar (ver `GET /roadmap`, campo `tem_questoes`).
--
-- FAIXAS DE ID, para não colidir com `seed_biologia_citologia.sql`, que já
-- ocupa materia 1, temas 1-3, subtemas 1-8 e questões 1-38:
--   materia   1..11   (1 é Biologia, o MESMO registro do seed existente)
--   tema      100..132
--   subtema   100..198
--
-- Idempotente: `ON CONFLICT (id) DO NOTHING` em toda inserção, e os
-- `setval` no fim reposicionam as sequences para que inserções pela API
-- (ex.: `scripts/ingest_enem.py`) não colidam com estes ids.
--
-- `videoaula_base_url`, `videoaula_revisao_url` e `descricao_ia` ficam
-- NULL: as duas primeiras são links de apoio (a rota de recomendação já
-- serializa `video_url: null` sem quebrar) e a terceira é sinal semântico
-- opcional (`f"{s.nome}. {s.descricao_ia or ''}"` em
-- `services/recomendacao_semantica.py`). Preenchê-las é melhoria por
-- matéria, não pré-requisito desta entrega.

INSERT INTO materia (id, nome) VALUES
(1, 'Biologia'),
(2, 'Física'),
(3, 'Química'),
(4, 'Matemática'),
(5, 'Português'),
(6, 'Literatura'),
(7, 'Inglês'),
(8, 'História'),
(9, 'Geografia'),
(10, 'Filosofia'),
(11, 'Sociologia')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tema (id, materia_id, nome, ordem) VALUES
(100, 1, 'Ecologia', 1),
(101, 1, 'Fisiologia Humana', 2),
(102, 1, 'Evolução', 3),
(103, 2, 'Mecânica', 1),
(104, 2, 'Termologia e Óptica', 2),
(105, 2, 'Eletricidade e Magnetismo', 3),
(106, 3, 'Química Geral', 1),
(107, 3, 'Físico-Química', 2),
(108, 3, 'Química Orgânica', 3),
(109, 4, 'Álgebra e Funções', 1),
(110, 4, 'Geometria', 2),
(111, 4, 'Estatística e Probabilidade', 3),
(112, 5, 'Gramática e Norma', 1),
(113, 5, 'Interpretação de Texto', 2),
(114, 5, 'Variação Linguística', 3),
(115, 6, 'Escolas Literárias', 1),
(116, 6, 'Modernismo Brasileiro', 2),
(117, 6, 'Análise Literária', 3),
(118, 7, 'Compreensão de Texto', 1),
(119, 7, 'Vocabulário e Cognatos', 2),
(120, 7, 'Estruturas Gramaticais', 3),
(121, 8, 'Brasil Colônia e Império', 1),
(122, 8, 'Brasil República', 2),
(123, 8, 'História Geral e Contemporânea', 3),
(124, 9, 'Geografia Física', 1),
(125, 9, 'Geopolítica e Globalização', 2),
(126, 9, 'Geografia do Brasil', 3),
(127, 10, 'Filosofia Antiga', 1),
(128, 10, 'Filosofia Moderna', 2),
(129, 10, 'Ética e Política', 3),
(130, 11, 'Formação da Sociologia', 1),
(131, 11, 'Trabalho e Sociedade', 2),
(132, 11, 'Cultura e Cidadania', 3)
ON CONFLICT (id) DO NOTHING;

INSERT INTO subtema (id, tema_id, nome, ordem, videoaula_base_url, videoaula_revisao_url, descricao_ia) VALUES
(100, 100, 'Ecossistemas e Cadeias Alimentares', 1, NULL, NULL, NULL),
(101, 100, 'Ciclos Biogeoquímicos', 2, NULL, NULL, NULL),
(102, 100, 'Impactos Ambientais', 3, NULL, NULL, NULL),
(103, 101, 'Sistema Digestório', 1, NULL, NULL, NULL),
(104, 101, 'Sistema Circulatório e Respiratório', 2, NULL, NULL, NULL),
(105, 101, 'Sistema Nervoso e Endócrino', 3, NULL, NULL, NULL),
(106, 102, 'Origem da Vida', 1, NULL, NULL, NULL),
(107, 102, 'Seleção Natural', 2, NULL, NULL, NULL),
(108, 102, 'Especiação e Evidências', 3, NULL, NULL, NULL),
(109, 103, 'Cinemática', 1, NULL, NULL, NULL),
(110, 103, 'Leis de Newton', 2, NULL, NULL, NULL),
(111, 103, 'Trabalho e Energia', 3, NULL, NULL, NULL),
(112, 104, 'Temperatura e Calor', 1, NULL, NULL, NULL),
(113, 104, 'Leis da Termodinâmica', 2, NULL, NULL, NULL),
(114, 104, 'Reflexão e Refração', 3, NULL, NULL, NULL),
(115, 105, 'Carga e Campo Elétrico', 1, NULL, NULL, NULL),
(116, 105, 'Circuitos Elétricos', 2, NULL, NULL, NULL),
(117, 105, 'Campo Magnético e Indução', 3, NULL, NULL, NULL),
(118, 106, 'Estrutura Atômica', 1, NULL, NULL, NULL),
(119, 106, 'Tabela Periódica', 2, NULL, NULL, NULL),
(120, 106, 'Ligações Químicas', 3, NULL, NULL, NULL),
(121, 107, 'Soluções e Concentração', 1, NULL, NULL, NULL),
(122, 107, 'Termoquímica', 2, NULL, NULL, NULL),
(123, 107, 'Equilíbrio Químico', 3, NULL, NULL, NULL),
(124, 108, 'Funções Orgânicas', 1, NULL, NULL, NULL),
(125, 108, 'Isomeria', 2, NULL, NULL, NULL),
(126, 108, 'Reações Orgânicas', 3, NULL, NULL, NULL),
(127, 109, 'Função Afim e Quadrática', 1, NULL, NULL, NULL),
(128, 109, 'Função Exponencial e Logarítmica', 2, NULL, NULL, NULL),
(129, 109, 'Progressões', 3, NULL, NULL, NULL),
(130, 110, 'Geometria Plana', 1, NULL, NULL, NULL),
(131, 110, 'Geometria Espacial', 2, NULL, NULL, NULL),
(132, 110, 'Geometria Analítica', 3, NULL, NULL, NULL),
(133, 111, 'Medidas de Tendência Central', 1, NULL, NULL, NULL),
(134, 111, 'Análise Combinatória', 2, NULL, NULL, NULL),
(135, 111, 'Probabilidade', 3, NULL, NULL, NULL),
(136, 112, 'Classes de Palavras', 1, NULL, NULL, NULL),
(137, 112, 'Sintaxe do Período', 2, NULL, NULL, NULL),
(138, 112, 'Concordância e Regência', 3, NULL, NULL, NULL),
(139, 113, 'Gêneros Textuais', 1, NULL, NULL, NULL),
(140, 113, 'Coesão e Coerência', 2, NULL, NULL, NULL),
(141, 113, 'Figuras de Linguagem', 3, NULL, NULL, NULL),
(142, 114, 'Norma-Padrão e Variedades', 1, NULL, NULL, NULL),
(143, 114, 'Registro e Adequação', 2, NULL, NULL, NULL),
(144, 114, 'Preconceito Linguístico', 3, NULL, NULL, NULL),
(145, 115, 'Barroco e Arcadismo', 1, NULL, NULL, NULL),
(146, 115, 'Romantismo', 2, NULL, NULL, NULL),
(147, 115, 'Realismo e Naturalismo', 3, NULL, NULL, NULL),
(148, 116, 'Primeira Geração', 1, NULL, NULL, NULL),
(149, 116, 'Segunda Geração', 2, NULL, NULL, NULL),
(150, 116, 'Terceira Geração', 3, NULL, NULL, NULL),
(151, 117, 'Prosa e Narrativa', 1, NULL, NULL, NULL),
(152, 117, 'Poesia e Métrica', 2, NULL, NULL, NULL),
(153, 117, 'Contexto Histórico da Obra', 3, NULL, NULL, NULL),
(154, 118, 'Skimming e Scanning', 1, NULL, NULL, NULL),
(155, 118, 'Ideia Principal e Detalhes', 2, NULL, NULL, NULL),
(156, 118, 'Inferência de Sentido', 3, NULL, NULL, NULL),
(157, 119, 'Cognatos e Falsos Cognatos', 1, NULL, NULL, NULL),
(158, 119, 'Phrasal Verbs', 2, NULL, NULL, NULL),
(159, 119, 'Afixos e Formação de Palavras', 3, NULL, NULL, NULL),
(160, 120, 'Verb Tenses', 1, NULL, NULL, NULL),
(161, 120, 'Modal Verbs', 2, NULL, NULL, NULL),
(162, 120, 'Conectivos e Referência', 3, NULL, NULL, NULL),
(163, 121, 'Colonização e Economia Açucareira', 1, NULL, NULL, NULL),
(164, 121, 'Mineração e Inconfidências', 2, NULL, NULL, NULL),
(165, 121, 'Independência e Segundo Reinado', 3, NULL, NULL, NULL),
(166, 122, 'República Velha', 1, NULL, NULL, NULL),
(167, 122, 'Era Vargas', 2, NULL, NULL, NULL),
(168, 122, 'Ditadura Militar e Redemocratização', 3, NULL, NULL, NULL),
(169, 123, 'Revolução Industrial', 1, NULL, NULL, NULL),
(170, 123, 'Guerras Mundiais', 2, NULL, NULL, NULL),
(171, 123, 'Guerra Fria e Descolonização', 3, NULL, NULL, NULL),
(172, 124, 'Relevo e Solos', 1, NULL, NULL, NULL),
(173, 124, 'Clima e Vegetação', 2, NULL, NULL, NULL),
(174, 124, 'Hidrografia', 3, NULL, NULL, NULL),
(175, 125, 'Blocos Econômicos', 1, NULL, NULL, NULL),
(176, 125, 'Conflitos e Fronteiras', 2, NULL, NULL, NULL),
(177, 125, 'Fluxos Migratórios', 3, NULL, NULL, NULL),
(178, 126, 'Regionalização', 1, NULL, NULL, NULL),
(179, 126, 'Urbanização e Metrópoles', 2, NULL, NULL, NULL),
(180, 126, 'Agropecuária e Indústria', 3, NULL, NULL, NULL),
(181, 127, 'Pré-Socráticos', 1, NULL, NULL, NULL),
(182, 127, 'Sócrates e Platão', 2, NULL, NULL, NULL),
(183, 127, 'Aristóteles', 3, NULL, NULL, NULL),
(184, 128, 'Racionalismo e Empirismo', 1, NULL, NULL, NULL),
(185, 128, 'Contratualismo', 2, NULL, NULL, NULL),
(186, 128, 'Kant e o Iluminismo', 3, NULL, NULL, NULL),
(187, 129, 'Ética e Moral', 1, NULL, NULL, NULL),
(188, 129, 'Poder e Estado', 2, NULL, NULL, NULL),
(189, 129, 'Direitos Humanos', 3, NULL, NULL, NULL),
(190, 130, 'Durkheim', 1, NULL, NULL, NULL),
(191, 130, 'Weber', 2, NULL, NULL, NULL),
(192, 130, 'Marx', 3, NULL, NULL, NULL),
(193, 131, 'Divisão Social do Trabalho', 1, NULL, NULL, NULL),
(194, 131, 'Taylorismo e Fordismo', 2, NULL, NULL, NULL),
(195, 131, 'Trabalho na Era Digital', 3, NULL, NULL, NULL),
(196, 132, 'Cultura e Identidade', 1, NULL, NULL, NULL),
(197, 132, 'Movimentos Sociais', 2, NULL, NULL, NULL),
(198, 132, 'Cidadania e Desigualdade', 3, NULL, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- materias 1..11, temas 100..132, subtemas 100..198

-- Sequences reposicionadas, mesmo padrão do seed de Citologia.
SELECT setval('materia_id_seq', (SELECT MAX(id) FROM materia));
SELECT setval('tema_id_seq', (SELECT MAX(id) FROM tema));
SELECT setval('subtema_id_seq', (SELECT MAX(id) FROM subtema));
