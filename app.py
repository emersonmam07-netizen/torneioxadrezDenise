import math
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

DB_NAME = 'torneio_xadrez.db'

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
                escola TEXT DEFAULT 'Escola Municipal',
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

    # MIGRAÇÃO AUTOMÁTICA DE COLUNAS
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

    # Sincronização automática de torneios existentes
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
    page_title='Gestão de Torneio Escolar de Xadrez', page_icon='♟️', layout='wide'
)

st.title('♟️ Sistema de Torneio Escolar de Xadrez')

aba = st.sidebar.radio(
    'Navegação',
    [
        '👥 Inscrição de Jogadores',
        '⚔️ Emparceiramento & Partidas',
        '📊 Classificação por Turma & Rodada',
        '⏱️ Cronômetro da Sala',
    ],
)

# -----------------------------------------------------------------------------
# ABA 1: INSCRIÇÃO DE JOGADORES
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
      turma_lote = st.text_input('Turma (Ex: 6º Ano A)')
      escola_lote = st.text_input('Escola', value='Escola Municipal')
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
      turma = st.text_input('Turma (Ex: 6º Ano A)')
      escola = st.text_input('Escola', value='Escola Municipal')
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
    st.write('### ⚙️ Opções de Exclusão')
    if not df_jogadores.empty:
      turmas_existentes = df_jogadores['turma'].unique().tolist()
      turma_del = st.selectbox('Selecione uma turma:', turmas_existentes)

      if st.button('🗑️ Excluir Turma e seus Alunos', type='secondary'):
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
# ABA 2: EMPARCEIRAMENTO E RODADAS ISOLADAS POR TURMA
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

      # Maior rodada criada para ESTA TURMA especificamente
      cursor.execute(
          'SELECT MAX(rodada) FROM partidas WHERE torneio_id = ?;', (torneio_id,)
      )
      res_max = cursor.fetchone()[0]
      max_rodada = res_max if res_max is not None else 0

      # Verificar se existem partidas sem resultado para ESTA TURMA na rodada atual
      cursor.execute(
          'SELECT COUNT(*) FROM partidas WHERE torneio_id = ? AND rodada = ?'
          ' AND resultado IS NULL;',
          (torneio_id, max_rodada),
      )
      partidas_pendentes = (cursor.fetchone()[0] > 0) if max_rodada > 0 else False

    rodada_ativa = max_rodada if partidas_pendentes else max_rodada + 1

    # Menu para visualizar historico de rodadas anteriores da mesma turma
    if max_rodada > 0:
      rodadas_disponiveis = list(range(1, max_rodada + 1))
      rodada_visualizar = st.selectbox(
          '📍 Selecione a Rodada para Visualizar / Lançar:',
          options=rodadas_disponiveis,
          index=len(rodadas_disponiveis) - 1,
      )
    else:
      rodada_visualizar = 1

    st.header(f'⚔️ {torneio_selecionado} — Rodada {rodada_visualizar}')

    # Botão para gerar NOVO emparceiramento (somente se a última rodada estiver 100% concluída)
    if not partidas_pendentes and rodada_visualizar == max_rodada:
      if st.button(
          f'🚀 Gerar Rodada {rodada_ativa} para {torneio_selecionado}',
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

          if len(df_j) < 2:
            st.warning(
                f'A turma {turma_nome} precisa de pelo menos 2 alunos'
                ' cadastrados.'
            )
          else:
            # Consulta partidas anteriores EXCLUSIVAMENTE deste torneio
            df_hist = pd.read_sql_query(
                'SELECT brancas_id, pretas_id FROM partidas WHERE torneio_id'
                ' = ? AND pretas_id IS NOT NULL AND brancas_id IS NOT NULL;',
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

            # Atribuição de BYE (Folga)
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
            st.rerun()

    # Lançamento e exibição de partidas da rodada selecionada
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
          (torneio_id, rodada_visualizar),
      )
      partidas_rodada = cursor.fetchall()

    if partidas_rodada:
      st.subheader(
          f'📋 Lançamento de Resultados — Rodada {rodada_visualizar}'
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
# ABA 3: CLASSIFICAÇÃO POR TURMA
# -----------------------------------------------------------------------------
elif aba == '📊 Classificação por Turma & Rodada':
  st.header('🏆 Classificação do Torneio por Turma')

  with get_connection() as conn:
    df_turmas = pd.read_sql_query(
        'SELECT DISTINCT turma FROM jogadores;', conn
    )

  if df_turmas.empty:
    st.info('Nenhum aluno cadastrado no banco de dados.')
  else:
    turmas_list = ['Todas as Turmas'] + df_turmas['turma'].tolist()

    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
      turma_filtro = st.selectbox('🏫 Filtrar por Turma:', turmas_list)
    with col_f2:
      busca_nome = st.text_input('🔍 Buscar Aluno por Nome:')

    with get_connection() as conn:
      query = """
                SELECT nome AS [Nome do Aluno], turma AS [Turma], 
                       pontos AS [Pontos], vitorias AS [Vitórias (V)], 
                       empates AS [Empates (E)], derrotas AS [Derrotas (D)],
                       rating_inicial AS [Elo Inicial], rating_atual AS [Elo Atual],
                       (rating_atual - rating_inicial) AS [Variação Elo]
                FROM jogadores
            """
      condicoes = []
      params = []

      if turma_filtro != 'Todas as Turmas':
        condicoes.append('turma = ?')
        params.append(turma_filtro)

      if busca_nome.strip():
        condicoes.append('nome LIKE ?')
        params.append(f'%{busca_nome.strip()}%')

      if condicoes:
        query += ' WHERE ' + ' AND '.join(condicoes)

      query += ' ORDER BY pontos DESC, vitorias DESC, rating_atual DESC;'

      df_classificacao = pd.read_sql_query(query, conn, params=params)

    if not df_classificacao.empty:
      st.subheader('🥇 Pódio da Turma')
      col_p1, col_p2, col_p3 = st.columns(3)

      if len(df_classificacao) >= 1:
        j1 = df_classificacao.iloc[0]
        col_p1.metric(
            label='🥇 1º Lugar',
            value=j1['Nome do Aluno'],
            delta=(
                f"{j1['Pontos']} pts | {j1['Vitórias (V)']}V-{j1['Empates (E)']}E-{j1['Derrotas (D)']}D"
            ),
        )

      if len(df_classificacao) >= 2:
        j2 = df_classificacao.iloc[1]
        col_p2.metric(
            label='🥈 2º Lugar',
            value=j2['Nome do Aluno'],
            delta=(
                f"{j2['Pontos']} pts | {j2['Vitórias (V)']}V-{j2['Empates (E)']}E-{j2['Derrotas (D)']}D"
            ),
        )

      if len(df_classificacao) >= 3:
        j3 = df_classificacao.iloc[2]
        col_p3.metric(
            label='🥉 3º Lugar',
            value=j3['Nome do Aluno'],
            delta=(
                f"{j3['Pontos']} pts | {j3['Vitórias (V)']}V-{j3['Empates (E)']}E-{j3['Derrotas (D)']}D"
            ),
        )

      st.write('---')
      st.subheader('📜 Tabela Geral de Classificação')

      df_exibir = df_classificacao.copy()
      df_exibir.index = range(1, len(df_exibir) + 1)
      df_exibir.index.name = 'Posição'

      st.dataframe(df_exibir, use_container_width=True)

      csv = df_exibir.to_csv(index=True).encode('utf-8')
      st.download_button(
          label='📥 Baixar Tabela em CSV',
          data=csv,
          file_name=(
              f'classificacao_{turma_filtro.lower().replace(" ", "_")}.csv'
          ),
          mime='text/csv',
          use_container_width=True,
      )

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
