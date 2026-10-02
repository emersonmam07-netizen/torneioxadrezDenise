import math
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

DB_NAME = 'torneio_xadrez.db'

# URL pública da imagem do logótipo da EBM Denise Christiane Harms
LOGO_URL = 'https://i.ibb.co/3ykXG3G/logo-denise-harms.png'

# -----------------------------------------------------------------------------
# 1. BANCO DE DADOS (SQLITE)
# -----------------------------------------------------------------------------


def get_connection():
  conn = sqlite3.connect(DB_NAME)
  conn.execute('PRAGMA foreign_keys = ON;')
  return conn


def inicializar_banco():
  with get_connection() as conn:
    cursor = conn.cursor()

    # Tabela de Torneios
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS torneios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                turma TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'EM_ANDAMENTO'
            )
        """)

    # Tabela de Jogadores / Alunos
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS jogadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                turma TEXT NOT NULL,
                escola TEXT DEFAULT 'EBM Denise Christiane Harms',
                categoria TEXT DEFAULT 'Livre',
                rating_inicial INTEGER DEFAULT 1000,
                rating_atual INTEGER DEFAULT 1000,
                pontos REAL DEFAULT 0.0,
                vitorias INTEGER DEFAULT 0,
                empates INTEGER DEFAULT 0,
                derrotas INTEGER DEFAULT 0
            )
        """)

    # Tabela de Partidas
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS partidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rodada INTEGER NOT NULL,
                mesa INTEGER NOT NULL,
                brancas_id INTEGER NOT NULL,
                pretas_id INTEGER,
                resultado TEXT,
                variacao_elo_brancas INTEGER DEFAULT 0,
                variacao_elo_pretas INTEGER DEFAULT 0,
                torneio_id INTEGER
            )
        """)

    # MIGRAÇÕES AUTOMÁTICAS
    cursor.execute("PRAGMA table_info('jogadores');")
    colunas_j = [col[1] for col in cursor.fetchall()]
    if 'vitorias' not in colunas_j:
      cursor.execute('ALTER TABLE jogadores ADD COLUMN vitorias INTEGER DEFAULT 0;')
      cursor.execute('ALTER TABLE jogadores ADD COLUMN empates INTEGER DEFAULT 0;')
      cursor.execute('ALTER TABLE jogadores ADD COLUMN derrotas INTEGER DEFAULT 0;')

    cursor.execute("PRAGMA table_info('partidas');")
    colunas_p = [col[1] for col in cursor.fetchall()]
    if 'torneio_id' not in colunas_p:
      cursor.execute('ALTER TABLE partidas ADD COLUMN torneio_id INTEGER;')

    # Sincronização automática de torneios
    cursor.execute('SELECT DISTINCT turma FROM jogadores;')
    turmas_existentes = cursor.fetchall()
    for (t_nome,) in turmas_existentes:
      if t_nome and t_nome.strip():
        nome_torneio = f'Torneio {t_nome.strip()}'
        cursor.execute(
            'INSERT OR IGNORE INTO torneios (nome, turma) VALUES (?, ?);',
            (nome_torneio, t_nome.strip()),
        )

    conn.commit()


inicializar_banco()

# -----------------------------------------------------------------------------
# 2. SISTEMA DE RATING ELO
# -----------------------------------------------------------------------------


class SistemaElo:

  @staticmethod
  def calcular_expectativa(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))

  @classmethod
  def calcular_variacao(
      cls, rating_a: int, rating_b: int, resultado: float, k_factor: int = 32
  ) -> tuple[int, int]:
    exp_a = cls.calcular_expectativa(rating_a, rating_b)
    exp_b = cls.calcular_expectativa(rating_b, rating_a)

    var_a = round(k_factor * (resultado - exp_a))
    var_b = round(k_factor * ((1.0 - resultado) - exp_b))
    return var_a, var_b


# -----------------------------------------------------------------------------
# 3. INTERFACE PRINCIPAL
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title='Clube de Xadrez Denise Harms', page_icon='♟️', layout='wide'
)

# Renderização do logótipo e título
col_logo, col_titulo = st.columns([1, 5])

with col_logo:
  try:
    st.image('logo.png', width=120)
  except Exception:
    try:
      st.image(LOGO_URL, width=120)
    except Exception:
      st.write('♟️')

with col_titulo:
  st.title('Clube de Xadrez Denise Harms')
  st.caption(
      'Sistema de Torneios Escolares, Emparceiramento Suíço & Rating Elo'
  )

st.write('---')

aba = st.sidebar.radio(
    'Navegação',
    [
        '👥 Inscrição de Jogadores',
        '⚔️️ Emparceiramento & Partidas',
        '📊 Classificação & Ranking',
        '⏱️ Cronômetro da Sala',
    ],
)

# -----------------------------------------------------------------------------
# ABA 1: INSCRIÇÃO DE JOGADORES (COM EXCLUSÃO INDIVIDUAL)
# -----------------------------------------------------------------------------
if aba == '👥 Inscrição de Jogadores':
  st.header('Cadastrar Alunos e Criar Torneios por Turma')

  tipo_cadastro = st.radio(
      'Modo de Cadastro:',
      ['📋 Cadastro em Lote (Colar Lista)', '👤 Cadastro Individual'],
      horizontal=True,
  )
  st.write('---')

  if tipo_cadastro == '📋 Cadastro em Lote (Colar Lista)':
    col1, col2 = st.columns(2)
    with col1:
      turma_lote = st.text_input('Turma (Ex: 4º ano 01)')
      escola_lote = st.text_input(
          'Escola', value='EBM Denise Christiane Harms'
      )
    with col2:
      categoria_lote = st.selectbox(
          'Categoria', ['Sub-10', 'Sub-12', 'Sub-14', 'Sub-18', 'Livre']
      )
      rating_inicial_lote = st.number_input('Rating Inicial', value=1000, step=25)

    lista_nomes = st.text_area(
        'Cole a lista de nomes (um por linha):',
        height=180,
        placeholder='Ana Silva\nBruno Souza\nCarlos Eduardo',
    )

    if st.button(
        '🚀 Cadastrar Alunos e Criar Torneio da Turma',
        type='primary',
        use_container_width=True,
    ):
      if turma_lote.strip() and lista_nomes.strip():
        nomes = [n.strip() for n in lista_nomes.split('\n') if n.strip()]
        turma_limpa = turma_lote.strip()
        nome_torneio = f'Torneio {turma_limpa}'

        with get_connection() as conn:
          cursor = conn.cursor()
          cursor.execute(
              'INSERT OR IGNORE INTO torneios (nome, turma) VALUES (?, ?);',
              (nome_torneio, turma_limpa),
          )

          for nome in nomes:
            cursor.execute(
                """
                            INSERT INTO jogadores (nome, turma, escola, categoria, rating_inicial, rating_atual, pontos, vitorias, empates, derrotas)
                            VALUES (?, ?, ?, ?, ?, ?, 0.0, 0, 0, 0)
                        """,
                (
                    nome,
                    turma_limpa,
                    escola_lote,
                    categoria_lote,
                    rating_inicial_lote,
                    rating_inicial_lote,
                ),
            )
          conn.commit()

        st.success(
            f'🎉 {len(nomes)} alunos cadastrados! Torneio **"{nome_torneio}"**'
            ' criado.'
        )
        st.rerun()
      else:
        st.error('Preencha a turma e cole a lista de nomes.')

  else:
    col1, col2 = st.columns(2)
    with col1:
      nome = st.text_input('Nome do Aluno')
      turma = st.text_input('Turma (Ex: 4º ano 01)')
      escola = st.text_input('Escola', value='EBM Denise Christiane Harms')
    with col2:
      categoria = st.selectbox(
          'Categoria', ['Sub-10', 'Sub-12', 'Sub-14', 'Sub-18', 'Livre']
      )
      rating_inicial = st.number_input('Rating Inicial', value=1000, step=25)

    if st.button('Cadastrar Aluno', type='primary', use_container_width=True):
      if nome and turma.strip():
        turma_limpa = turma.strip()
        nome_torneio = f'Torneio {turma_limpa}'
        with get_connection() as conn:
          cursor = conn.cursor()
          cursor.execute(
              'INSERT OR IGNORE INTO torneios (nome, turma) VALUES (?, ?);',
              (nome_torneio, turma_limpa),
          )
          cursor.execute(
              """
                        INSERT INTO jogadores (nome, turma, escola, categoria, rating_inicial, rating_atual, pontos, vitorias, empates, derrotas)
                        VALUES (?, ?, ?, ?, ?, ?, 0.0, 0, 0, 0)
                    """,
              (
                  nome,
                  turma_limpa,
                  escola,
                  categoria,
                  rating_inicial,
                  rating_inicial,
              ),
          )
          conn.commit()
        st.success(
            f'Aluno **{nome}** cadastrado no **{nome_torneio}** com sucesso!'
        )
        st.rerun()

  st.divider()

  st.subheader('📋 Alunos e Torneios Cadastrados')

  with get_connection() as conn:
    df_jogadores = pd.read_sql_query('SELECT * FROM jogadores;', conn)
    df_torneios_view = pd.read_sql_query('SELECT * FROM torneios;', conn)

  col_v1, col_v2 = st.columns([3, 2])
  with col_v1:
    st.write('### 🏆 Torneios Ativos por Turma')
    st.dataframe(df_torneios_view, use_container_width=True)

  with col_v2:
    st.write('### ⚙️ Gerenciamento e Exclusão')
    if not df_jogadores.empty:

      # 1. EXCLUIR APENAS UM ALUNO (NOVO)
      st.markdown('#### 👤 Excluir um Aluno Específico')
      # Cria rótulo amigável: "Nome do Aluno (Turma)"
      df_jogadores['label_aluno'] = (
          df_jogadores['nome'] + ' (' + df_jogadores['turma'] + ')'
      )
      dict_alunos = dict(
          zip(df_jogadores['label_aluno'], df_jogadores['id'])
      )

      aluno_selecionado_label = st.selectbox(
          'Selecione o aluno para remover:',
          options=list(dict_alunos.keys()),
      )
      aluno_id_del = dict_alunos[aluno_selecionado_label]

      if st.button('🗑️ Excluir Aluno Selecionado', type='secondary'):
        with get_connection() as conn:
          cursor = conn.cursor()
          # Excluir partidas vinculadas ao aluno
          cursor.execute(
              'DELETE FROM partidas WHERE brancas_id = ? OR pretas_id = ?;',
              (aluno_id_del, aluno_id_del),
          )
          # Excluir jogador
          cursor.execute(
              'DELETE FROM jogadores WHERE id = ?;', (aluno_id_del,)
          )
          conn.commit()
        st.success(f'Aluno "{aluno_selecionado_label}" removido com sucesso!')
        st.rerun()

      st.write('---')

      # 2. EXCLUIR UMA TURMA INTEIRA
      st.markdown('#### 🏫 Excluir Turma Inteira')
      turmas_existentes = df_jogadores['turma'].unique().tolist()
      turma_del = st.selectbox(
          'Selecione a turma para remover:', turmas_existentes
      )

      if st.button('🗑️ Excluir Turma e Todos os seus Alunos', type='secondary'):
        with get_connection() as conn:
          cursor = conn.cursor()
          cursor.execute(
              'DELETE FROM partidas WHERE brancas_id IN (SELECT id FROM'
              ' jogadores WHERE turma = ?) OR pretas_id IN (SELECT id FROM'
              ' jogadores WHERE turma = ?);',
              (turma_del, turma_del),
          )
          cursor.execute(
              'DELETE FROM jogadores WHERE turma = ?;', (turma_del,)
          )
          cursor.execute('DELETE FROM torneios WHERE turma = ?;', (turma_del,))
          conn.commit()
        st.success(f'Turma "{turma_del}" removida!')
        st.rerun()

      st.write('---')

      # 3. RESETAR BANCO DE DADOS COMPLETO
      if st.button('💥 RESETAR TODO O BANCO DE DADOS', type='primary'):
        with get_connection() as conn:
          cursor = conn.cursor()
          cursor.execute('DELETE FROM partidas;')
          cursor.execute('DELETE FROM jogadores;')
          cursor.execute('DELETE FROM torneios;')
          conn.commit()
        st.rerun()

  st.write('### 👤 Lista Geral de Alunos')
  st.dataframe(df_jogadores, use_container_width=True)

# -----------------------------------------------------------------------------
# ABA 2: EMPARCEIRAMENTO E LANÇAMENTO DE RESULTADOS
# -----------------------------------------------------------------------------
elif aba == '⚔️ Emparceiramento & Partidas':
  with get_connection() as conn:
    df_torneios = pd.read_sql_query('SELECT * FROM torneios;', conn)

  if df_torneios.empty:
    st.warning(
        'Nenhum torneio/turma encontrado. Cadastre os alunos da turma na'
        ' primeira aba para criar o torneio automaticamente.'
    )
  else:
    torneio_selecionado = st.selectbox(
        '🏆 Selecione o Torneio da Turma:',
        df_torneios['nome'].tolist(),
    )
    torneio_info = df_torneios[
        df_torneios['nome'] == torneio_selecionado
    ].iloc[0]
    torneio_id = int(torneio_info['id'])
    turma_nome = torneio_info['turma']

    with get_connection() as conn:
      cursor = conn.cursor()

      cursor.execute(
          'SELECT COUNT(*) FROM jogadores WHERE turma = ?;', (turma_nome,)
      )
      total_alunos_turma = cursor.fetchone()[0]

      cursor.execute(
          'SELECT MAX(rodada) FROM partidas WHERE torneio_id = ?;', (torneio_id,)
      )
      res_max = cursor.fetchone()[0]
      max_rodada = res_max if res_max is not None else 0

      cursor.execute(
          'SELECT COUNT(*) FROM partidas WHERE torneio_id = ? AND rodada = ?'
          ' AND resultado IS NULL;',
          (torneio_id, max_rodada),
      )
      partidas_pendentes = (cursor.fetchone()[0] > 0) if max_rodada > 0 else False

    rodada_ativa = max_rodada if partidas_pendentes else max_rodada + 1

    st.header(f'⚔️ {torneio_selecionado} — Rodada {rodada_ativa}')

    if total_alunos_turma < 2:
      st.error(
          f'⚠️️ A turma "{turma_nome}" possui apenas {total_alunos_turma}'
          ' aluno(s) cadastrado(s). Cadastre pelo menos 2 alunos para iniciar o'
          ' torneio.'
      )
    elif partidas_pendentes:
      st.warning(
          f'⚠️ A Rodada {max_rodada} possui partidas sem resultado. Preencha e'
          ' confirme os resultados abaixo para liberar a próxima rodada.'
      )
    else:
      if st.button(
          f'🚀 Gerar Emparceiramento — Rodada {rodada_ativa}',
          type='primary',
          use_container_width=True,
      ):
        with get_connection() as conn:
          df_j = pd.read_sql_query(
              'SELECT * FROM jogadores WHERE turma = ? ORDER BY pontos DESC,'
              ' rating_atual DESC;',
              conn,
              params=(turma_nome,),
          )

          df_hist = pd.read_sql_query(
              'SELECT brancas_id, pretas_id FROM partidas WHERE torneio_id = ?'
              ' AND pretas_id IS NOT NULL AND brancas_id IS NOT NULL;',
              conn,
              params=(torneio_id,),
          )
          historico_pares = set()
          for _, row_h in df_hist.iterrows():
            historico_pares.add(
                (int(row_h['brancas_id']), int(row_h['pretas_id']))
            )
            historico_pares.add(
                (int(row_h['pretas_id']), int(row_h['brancas_id']))
            )

          livres = df_j.to_dict('records')
          confrontos = []

          while len(livres) > 1:
            j1 = livres.pop(0)
            j2 = None

            for cand in livres:
              if (j1['id'], cand['id']) not in historico_pares:
                j2 = cand
                break

            if not j2:
              j2 = livres[0]

            livres.remove(j2)
            confrontos.append((j1, j2))

          cursor = conn.cursor()
          mesa = 1
          for j1, j2 in confrontos:
            cursor.execute(
                """
                            INSERT INTO partidas (torneio_id, rodada, mesa, brancas_id, pretas_id)
                            VALUES (?, ?, ?, ?, ?)
                        """,
                (torneio_id, rodada_ativa, mesa, j1['id'], j2['id']),
            )
            mesa += 1

          if livres:
            j_bye = livres[0]
            cursor.execute(
                """
                            INSERT INTO partidas (torneio_id, rodada, mesa, brancas_id, pretas_id, resultado)
                            VALUES (?, ?, ?, ?, NULL, 'BYE')
                        """,
                (torneio_id, rodada_ativa, mesa, j_bye['id']),
            )
            cursor.execute(
                'UPDATE jogadores SET pontos = pontos + 1.0, vitorias ='
                ' vitorias + 1 WHERE id = ?;',
                (j_bye['id'],),
            )

          conn.commit()
          st.success(f'Rodada {rodada_ativa} gerada!')
          st.rerun()

    rodada_exibir = max_rodada if max_rodada > 0 else 1
    with get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute(
          """
                SELECT p.id, p.mesa, p.resultado,
                       j1.id as b_id, j1.nome as b_nome, j1.turma as b_turma, j1.rating_atual as b_rating,
                       j2.id as p_id, j2.nome as p_nome, j2.turma as p_turma, j2.rating_atual as p_rating
                FROM partidas p
                JOIN jogadores j1 ON p.brancas_id = j1.id
                LEFT JOIN jogadores j2 ON p.pretas_id = j2.id
                WHERE p.torneio_id = ? AND p.rodada = ?
                ORDER BY p.mesa ASC;
            """,
          (torneio_id, rodada_exibir),
      )
      partidas_rodada = cursor.fetchall()

    if partidas_rodada:
      st.subheader(
          f'📋 Lançamento de Resultados — Rodada {rodada_exibir}'
          f' ({torneio_selecionado})'
      )
      with st.form('form_resultados'):
        res_inputs = {}

        for row in partidas_rodada:
          (
              p_id,
              mesa,
              res_atual,
              b_id,
              b_nome,
              b_turma,
              b_rating,
              p_id_atleta,
              p_nome,
              p_turma,
              p_rating,
          ) = row

          col_m, col_p, col_r = st.columns([1, 4, 3])
          with col_m:
            st.markdown(f'### **Mesa {mesa}**')

          with col_p:
            if p_id_atleta is None:
              st.success(f'**{b_nome}** — *Folga (BYE)*')
            else:
              st.write(f'⚪ **Brancas:** {b_nome} (Elo: {b_rating})')
              st.write(f'⚫ **Pretas:** {p_nome} (Elo: {p_rating})')

          with col_r:
            if p_id_atleta is not None:
              if res_atual is not None:
                st.info(f'Resultado Lançado: **{res_atual}**')
              else:
                res_inputs[p_id] = {
                    'b_id': b_id,
                    'p_id': p_id_atleta,
                    'b_nome': b_nome,
                    'p_nome': p_nome,
                    'b_rating': b_rating,
                    'p_rating': p_rating,
                    'opcao': st.selectbox(
                        'Vencedor',
                        options=['Brancas Vencem', 'Empate', 'Pretas Vencem'],
                        key=f'mesa_db_{mesa}',
                    ),
                }

          st.write('---')

        if res_inputs and st.form_submit_button(
            'Confirmar Resultados no Banco',
            type='primary',
            use_container_width=True,
        ):
          with get_connection() as conn:
            cursor = conn.cursor()

            for p_id_db, dados in res_inputs.items():
              opcao = dados['opcao']
              b_id, p_id_atl = dados['b_id'], dados['p_id']

              if opcao == 'Brancas Vencem':
                res_str = '1-0'
                score_b = 1.0
                v_b, e_b, d_b = 1, 0, 0
                v_p, e_p, d_p = 0, 0, 1
                pts_b, pts_p = 1.0, 0.0
              elif opcao == 'Pretas Vencem':
                res_str = '0-1'
                score_b = 0.0
                v_b, e_b, d_b = 0, 0, 1
                v_p, e_p, d_p = 1, 0, 0
                pts_b, pts_p = 0.0, 1.0
              else:  # Empate
                res_str = '0.5-0.5'
                score_b = 0.5
                v_b, e_b, d_b = 0, 1, 0
                v_p, e_p, d_p = 0, 1, 0
                pts_b, pts_p = 0.5, 0.5

              var_b, var_p = SistemaElo.calcular_variacao(
                  dados['b_rating'], dados['p_rating'], score_b
              )

              # Atualizar Partida
              cursor.execute(
                  """
                                UPDATE partidas 
                                SET resultado = ?, variacao_elo_brancas = ?, variacao_elo_pretas = ?
                                WHERE id = ?;
                            """,
                  (res_str, var_b, var_p, p_id_db),
              )

              # Atualizar Jogador Brancas
              cursor.execute(
                  """
                                UPDATE jogadores 
                                SET pontos = pontos + ?, rating_atual = rating_atual + ?,
                                    vitorias = vitorias + ?, empates = empates + ?, derrotas = derrotas + ?
                                WHERE id = ?;
                            """,
                  (pts_b, var_b, v_b, e_b, d_b, b_id),
              )

              # Atualizar Jogador Pretas
              cursor.execute(
                  """
                                UPDATE jogadores 
                                SET pontos = pontos + ?, rating_atual = rating_atual + ?,
                                    vitorias = vitorias + ?, empates = empates + ?, derrotas = derrotas + ?
                                WHERE id = ?;
                            """,
                  (pts_p, var_p, v_p, e_p, d_p, p_id_atl),
              )

            conn.commit()
          st.success('Resultados gravados com sucesso!')
          st.rerun()

# -----------------------------------------------------------------------------
# ABA 3: RANKING POR TURMA E RANKING GERAL
# -----------------------------------------------------------------------------
elif aba == '📊 Classificação & Ranking':
  st.header('🏆 Quadro de Classificação & Rankings')

  tab_turma, tab_geral = st.tabs(
      ['🏫 Ranking por Turma', '🌍 Ranking Geral (Escola)']
  )

  # ---------------------------------------------------------------------------
  # TAB 1: RANKING POR TURMA
  # ---------------------------------------------------------------------------
  with tab_turma:
    with get_connection() as conn:
      df_turmas = pd.read_sql_query(
          'SELECT DISTINCT turma FROM jogadores;', conn
      )

    if df_turmas.empty:
      st.info('Nenhum aluno cadastrado no banco de dados.')
    else:
      col_f1, col_f2 = st.columns([2, 2])
      with col_f1:
        turma_filtro = st.selectbox(
            'Selecione a Turma:', df_turmas['turma'].tolist()
        )
      with col_f2:
        busca_nome_t = st.text_input('🔍 Buscar Aluno na Turma:')

      with get_connection() as conn:
        query_t = """
                    SELECT nome AS [Nome do Aluno], turma AS [Turma], 
                           pontos AS [Pontos], vitorias AS [Vitórias (V)], 
                           empates AS [Empates (E)], derrotas AS [Derrotas (D)],
                           rating_inicial AS [Elo Inicial], rating_atual AS [Elo Atual],
                           (rating_atual - rating_inicial) AS [Variação Elo]
                    FROM jogadores
                    WHERE turma = ?
                """
        params_t = [turma_filtro]

        if busca_nome_t.strip():
          query_t += ' AND nome LIKE ?'
          params_t.append(f'%{busca_nome_t.strip()}%')

        query_t += ' ORDER BY pontos DESC, vitorias DESC, rating_atual DESC;'

        df_classif_turma = pd.read_sql_query(query_t, conn, params=params_t)

      if not df_classif_turma.empty:
        st.subheader(f'🥇 Pódio — {turma_filtro}')
        col_p1, col_p2, col_p3 = st.columns(3)

        if len(df_classif_turma) >= 1:
          j1 = df_classif_turma.iloc[0]
          col_p1.metric(
              label='🥇 1º Lugar',
              value=j1['Nome do Aluno'],
              delta=(
                  f"{j1['Pontos']} pts | {j1['Vitórias (V)']}V-{j1['Empates (E)']}E-{j1['Derrotas (D)']}D"
              ),
          )

        if len(df_classif_turma) >= 2:
          j2 = df_classif_turma.iloc[1]
          col_p2.metric(
              label='🥈 2º Lugar',
              value=j2['Nome do Aluno'],
              delta=(
                  f"{j2['Pontos']} pts | {j2['Vitórias (V)']}V-{j2['Empates (E)']}E-{j2['Derrotas (D)']}D"
              ),
          )

        if len(df_classif_turma) >= 3:
          j3 = df_classif_turma.iloc[2]
          col_p3.metric(
              label='🥉 3º Lugar',
              value=j3['Nome do Aluno'],
              delta=(
                  f"{j3['Pontos']} pts | {j3['Vitórias (V)']}V-{j3['Empates (E)']}E-{j3['Derrotas (D)']}D"
              ),
          )

        st.write('---')
        st.subheader(f'📜 Tabela Oficial — {turma_filtro}')

        df_exibir_t = df_classif_turma.copy()
        df_exibir_t.index = range(1, len(df_exibir_t) + 1)
        df_exibir_t.index.name = 'Posição'

        st.dataframe(df_exibir_t, use_container_width=True)

        csv_t = df_exibir_t.to_csv(index=True).encode('utf-8')
        st.download_button(
            label=f'📥 Baixar Ranking do {turma_filtro} (CSV)',
            data=csv_t,
            file_name=(
                f'ranking_{turma_filtro.lower().replace(" ", "_")}.csv'
            ),
            mime='text/csv',
            use_container_width=True,
        )

  # ---------------------------------------------------------------------------
  # TAB 2: RANKING GERAL (ESCOLA INTEIRA)
  # ---------------------------------------------------------------------------
  with tab_geral:
    st.subheader(
        '🌍 Ranking Geral Unificado (EBM Denise Christiane Harms)'
    )

    busca_nome_g = st.text_input('🔍 Buscar Aluno no Ranking Geral:')

    with get_connection() as conn:
      query_g = """
                SELECT nome AS [Nome do Aluno], turma AS [Turma], escola AS [Escola],
                       pontos AS [Pontos], vitorias AS [Vitórias (V)], 
                       empates AS [Empates (E)], derrotas AS [Derrotas (D)],
                       rating_inicial AS [Elo Inicial], rating_atual AS [Elo Atual],
                       (rating_atual - rating_inicial) AS [Variação Elo]
                FROM jogadores
            """
      params_g = []

      if busca_nome_g.strip():
        query_g += ' WHERE nome LIKE ?'
        params_g.append(f'%{busca_nome_g.strip()}%')

      query_g += ' ORDER BY pontos DESC, vitorias DESC, rating_atual DESC;'

      df_classif_geral = pd.read_sql_query(query_g, conn, params=params_g)

    if not df_classif_geral.empty:
      m1, m2, m3 = st.columns(3)
      m1.metric('👥 Total de Alunos', len(df_classif_geral))
      m2.metric(
          '🏫 Total de Turmas', df_classif_geral['Turma'].nunique()
      )
      m3.metric('⭐ Maior Rating Elo', int(df_classif_geral['Elo Atual'].max()))

      st.write('---')

      st.subheader('👑 Top 3 Geral da Escola')
      col_g1, col_g2, col_g3 = st.columns(3)

      if len(df_classif_geral) >= 1:
        g1 = df_classif_geral.iloc[0]
        col_g1.metric(
            label='🥇 1º Lugar Geral',
            value=f"{g1['Nome do Aluno']} ({g1['Turma']})",
            delta=f"{g1['Pontos']} pts | Elo {g1['Elo Atual']}",
        )

      if len(df_classif_geral) >= 2:
        g2 = df_classif_geral.iloc[1]
        col_g2.metric(
            label='🥈 2º Lugar Geral',
            value=f"{g2['Nome do Aluno']} ({g2['Turma']})",
            delta=f"{g2['Pontos']} pts | Elo {g2['Elo Atual']}",
        )

      if len(df_classif_geral) >= 3:
        g3 = df_classif_geral.iloc[2]
        col_g3.metric(
            label='🥉 3º Lugar Geral',
            value=f"{g3['Nome do Aluno']} ({g3['Turma']})",
            delta=f"{g3['Pontos']} pts | Elo {g3['Elo Atual']}",
        )

      st.write('---')
      st.subheader('📜 Tabela de Classificação Geral')

      df_exibir_g = df_classif_geral.copy()
      df_exibir_g.index = range(1, len(df_exibir_g) + 1)
      df_exibir_g.index.name = 'Posição Geral'

      st.dataframe(df_exibir_g, use_container_width=True)

      csv_g = df_exibir_g.to_csv(index=True).encode('utf-8')
      st.download_button(
          label='📥 Baixar Ranking Geral da Escola (CSV)',
          data=csv_g,
          file_name='ranking_geral_escola.csv',
          mime='text/csv',
          use_container_width=True,
      )
    else:
      st.info('Nenhum aluno cadastrado no momento.')

# -----------------------------------------------------------------------------
# ABA 4: CRONÔMETRO
# -----------------------------------------------------------------------------
elif aba == '⏱️ Cronômetro da Sala':
  st.subheader('⏱️ Temporizador da Rodada (Projeção)')
  minutos = st.number_input(
      'Tempo da Rodada (minutos):', min_value=1, max_value=120, value=15, step=1
  )

  html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: sans-serif;
                background-color: #0e1117;
                color: #ffffff;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                margin: 0;
                padding: 10px;
            }}
            #timer {{
                font-size: 7rem;
                font-weight: bold;
                font-family: monospace;
                color: #00ff66;
                margin: 10px 0;
            }}
            .alerta {{ color: #ff3333 !important; }}
            button {{
                font-size: 1.2rem;
                padding: 10px 20px;
                margin: 5px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
            }}
            #startBtn {{ background-color: #28a745; color: white; }}
            #pauseBtn {{ background-color: #ffc107; color: black; }}
            #resetBtn {{ background-color: #dc3545; color: white; }}
        </style>
    </head>
    <body>
        <div id="timer">{minutos:02d}:00</div>
        <div>
            <button id="startBtn" onclick="iniciar()">▶️ Iniciar</button>
            <button id="pauseBtn" onclick="pausar()">⏸️ Pausar</button>
            <button id="resetBtn" onclick="reiniciar()">🔄 Reiniciar</button>
        </div>

        <script>
            let tempoTotal = {minutos} * 60;
            let tempoRestante = tempoTotal;
            let intervalo = null;
            let rodando = false;

            function tocarApito() {{
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                function bip(freq, inicio, duracao) {{
                    const osc = audioCtx.createOscillator();
                    const gain = audioCtx.createGain();
                    osc.type = 'sine';
                    osc.frequency.value = freq;
                    osc.connect(gain);
                    gain.connect(audioCtx.destination);
                    osc.start(audioCtx.currentTime + inicio);
                    osc.stop(audioCtx.currentTime + inicio + duracao);
                }}
                bip(880, 0, 0.2);
                bip(880, 0.3, 0.2);
                bip(1200, 0.6, 0.8);
            }}

            function atualizarDisplay() {{
                const min = Math.floor(tempoRestante / 60);
                const seg = tempoRestante % 60;
                const display = document.getElementById('timer');
                display.innerText = `${{String(min).padStart(2, '0')}}:${{String(seg).padStart(2, '0')}}`;
                if (tempoRestante <= 60) display.classList.add('alerta');
                else display.classList.remove('alerta');
            }}

            function iniciar() {{
                if (!rodando && tempoRestante > 0) {{
                    rodando = true;
                    intervalo = setInterval(() => {{
                        tempoRestante--;
                        atualizarDisplay();
                        if (tempoRestante <= 0) {{
                            clearInterval(intervalo);
                            rodando = false;
                            tocarApito();
                        }}
                    }}, 1000);
                }}
            }}

            function pausar() {{ clearInterval(intervalo); rodando = false; }}
            function reiniciar() {{
                clearInterval(intervalo);
                rodando = false;
                tempoRestante = {minutos} * 60;
                atualizarDisplay();
            }}
        </script>
    </body>
    </html>
    """

  components.html(html_code, height=280)
