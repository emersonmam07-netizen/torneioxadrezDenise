import math
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

DB_NAME = 'torneio_xadrez.db'

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DO BANCO DE DADOS (SQLITE)
# -----------------------------------------------------------------------------


def get_connection():
  conn = sqlite3.connect(DB_NAME)
  conn.execute('PRAGMA foreign_keys = ON;')
  return conn


def inicializar_banco():
  with get_connection() as conn:
    cursor = conn.cursor()

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
                pontos REAL DEFAULT 0.0
            )
        """)

    # Tabela de Partidas / Rodadas
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS partidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rodada INTEGER NOT NULL,
                mesa INTEGER NOT NULL,
                brancas_id INTEGER NOT NULL,
                pretas_id INTEGER, -- NULL representa Folga / BYE
                resultado TEXT, -- '1-0', '0-1', '0.5-0.5', 'BYE'
                variacao_elo_brancas INTEGER DEFAULT 0,
                variacao_elo_pretas INTEGER DEFAULT 0,
                FOREIGN KEY (brancas_id) REFERENCES jogadores (id),
                FOREIGN KEY (pretas_id) REFERENCES jogadores (id)
            )
        """)
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
# 3. INTERFACE PRINCIPAL (STREAMLIT)
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
# ABA 1: INSCRIÇÃO DE JOGADORES (INDIVIDUAL OU EM LOTE)
# -----------------------------------------------------------------------------
if aba == '👥 Inscrição de Jogadores':
  st.header('Cadastrar Alunos da Turma')

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
        '🚀 Cadastrar Todos os Alunos', type='primary', use_container_width=True
    ):
      if turma_lote and lista_nomes.strip():
        nomes = [n.strip() for n in lista_nomes.split('\n') if n.strip()]
        with get_connection() as conn:
          cursor = conn.cursor()
          for nome in nomes:
            cursor.execute(
                """
                            INSERT INTO jogadores (nome, turma, escola, categoria, rating_inicial, rating_atual, pontos)
                            VALUES (?, ?, ?, ?, ?, ?, 0.0)
                        """,
                (
                    nome,
                    turma_lote,
                    escola_lote,
                    categoria_lote,
                    rating_inicial_lote,
                    rating_inicial_lote,
                ),
            )
          conn.commit()
        st.success(f'🎉 {len(nomes)} alunos cadastrados com sucesso!')
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
      if nome and turma:
        with get_connection() as conn:
          cursor = conn.cursor()
          cursor.execute(
              """
                        INSERT INTO jogadores (nome, turma, escola, categoria, rating_inicial, rating_atual, pontos)
                        VALUES (?, ?, ?, ?, ?, ?, 0.0)
                    """,
              (
                  nome,
                  turma,
                  escola,
                  categoria,
                  rating_inicial,
                  rating_inicial,
              ),
          )
          conn.commit()
        st.success(f'Aluno **{nome}** cadastrado com sucesso!')
        st.rerun()

  st.divider()

  # Exibição dos alunos salvos e botão de reset
  col_t1, col_t2 = st.columns([4, 1])
  with col_t1:
    st.subheader('Alunos Inscritos')
  with col_t2:
    if st.button('🗑️ Resetar Torneio'):
      with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM partidas;')
        cursor.execute('DELETE FROM jogadores;')
        conn.commit()
      st.rerun()

  with get_connection() as conn:
    df_jogadores = pd.read_sql_query('SELECT * FROM jogadores;', conn)
  st.dataframe(df_jogadores, use_container_width=True)

# -----------------------------------------------------------------------------
# ABA 2: EMPARCEIRAMENTO E RESULTADOS
# -----------------------------------------------------------------------------
elif aba == '⚔️ Emparceiramento & Partidas':
  with get_connection() as conn:
    cursor = conn.cursor()

    # Identificar rodada atual
    cursor.execute('SELECT MAX(rodada) FROM partidas;')
    max_rodada = cursor.fetchone()[0] or 0

    # Verificar se existem partidas pendentes na rodada atual
    cursor.execute(
        'SELECT COUNT(*) FROM partidas WHERE rodada = ? AND resultado IS NULL;',
        (max_rodada,),
    )
    partidas_pendentes = cursor.fetchone()[0] > 0

  rodada_ativa = max_rodada if partidas_pendentes else max_rodada + 1
  st.header(f'Rodada {rodada_ativa}')

  # Botão de geração de novas mesas caso a rodada anterior tenha finalizado
  if not partidas_pendentes:
    if st.button(
        'Gerar Emparceiramento da Rodada',
        type='primary',
        use_container_width=True,
    ):
      with get_connection() as conn:
        df_j = pd.read_sql_query(
            'SELECT * FROM jogadores ORDER BY pontos DESC, rating_atual DESC;',
            conn,
        )

        if len(df_j) < 2:
          st.warning('Cadastre pelo menos 2 alunos no banco.')
        else:
          # Histórico de partidas anteriores para evitar repetição
          df_hist = pd.read_sql_query(
              'SELECT brancas_id, pretas_id FROM partidas WHERE pretas_id IS'
              ' NOT NULL;',
              conn,
          )
          historico_pares = set(
              zip(df_hist['brancas_id'], df_hist['pretas_id'])
          ) | set(zip(df_hist['pretas_id'], df_hist['brancas_id']))

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

          # Salvar emparceiramento no banco de dados
          cursor = conn.cursor()
          mesa = 1
          for j1, j2 in confrontos:
            cursor.execute(
                """
                            INSERT INTO partidas (rodada, mesa, brancas_id, pretas_id)
                            VALUES (?, ?, ?, ?)
                        """,
                (rodada_ativa, mesa, j1['id'], j2['id']),
            )
            mesa += 1

          # Tratamento de número ímpar de alunos (Folga / BYE)
          if livres:
            j_bye = livres[0]
            cursor.execute(
                """
                            INSERT INTO partidas (rodada, mesa, brancas_id, pretas_id, resultado)
                            VALUES (?, ?, ?, NULL, 'BYE')
                        """,
                (rodada_ativa, mesa, j_bye['id']),
            )
            cursor.execute(
                'UPDATE jogadores SET pontos = pontos + 1.0 WHERE id = ?;',
                (j_bye['id'],),
            )

          conn.commit()
          st.rerun()

  # Lançamento dos resultados
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
            WHERE p.rodada = ?
            ORDER BY p.mesa ASC;
        """,
        (rodada_ativa,),
    )
    partidas_rodada = cursor.fetchall()

  if partidas_rodada:
    st.subheader(f'📋 Lançamento de Resultados - Rodada {rodada_ativa}')
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
            st.success(f'**{b_nome}** ({b_turma}) — *Folga (BYE)*')
          else:
            st.write(f'⚪ **Brancas:** {b_nome} ({b_turma}) - Elo: {b_rating}')
            st.write(f'⚫ **Pretas:** {p_nome} ({p_turma}) - Elo: {p_rating}')

        with col_r:
          if p_id_atleta is not None:
            res_inputs[p_id] = {
                'b_id': b_id,
                'p_id': p_id_atleta,
                'b_nome': b_nome,
                'p_nome': p_nome,
                'b_rating': b_rating,
                'p_rating': p_rating,
                'opcao': st.selectbox(
                    'Vencedor',
                    options=[
                        f'Vitória de {b_nome}',
                        'Empate',
                        f'Vitória de {p_nome}',
                    ],
                    key=f'mesa_db_{mesa}',
                ),
            }

        st.write('---')

      if st.form_submit_button(
          'Confirmar Resultados no Banco',
          type='primary',
          use_container_width=True,
      ):
        with get_connection() as conn:
          cursor = conn.cursor()

          for p_id_db, dados in res_inputs.items():
            opcao = dados['opcao']
            b_id, p_id_atl = dados['b_id'], dados['p_id']

            if 'Vitória de' in opcao:
              vencedor_is_brancas = dados['b_nome'] in opcao
              res_str = '1-0' if vencedor_is_brancas else '0-1'
              score_b = 1.0 if vencedor_is_brancas else 0.0
              pts_b = 1.0 if vencedor_is_brancas else 0.0
              pts_p = 0.0 if vencedor_is_brancas else 1.0
            else:
              res_str = '0.5-0.5'
              score_b = 0.5
              pts_b, pts_p = 0.5, 0.5

            var_b, var_p = SistemaElo.calcular_variacao(
                dados['b_rating'], dados['p_rating'], score_b
            )

            cursor.execute(
                """
                            UPDATE partidas 
                            SET resultado = ?, variacao_elo_brancas = ?, variacao_elo_pretas = ?
                            WHERE id = ?;
                        """,
                (res_str, var_b, var_p, p_id_db),
            )

            cursor.execute(
                """
                            UPDATE jogadores 
                            SET pontos = pontos + ?, rating_atual = rating_atual + ?
                            WHERE id = ?;
                        """,
                (pts_b, var_b, b_id),
            )

            cursor.execute(
                """
                            UPDATE jogadores 
                            SET pontos = pontos + ?, rating_atual = rating_atual + ?
                            WHERE id = ?;
                        """,
                (pts_p, var_p, p_id_atl),
            )

          conn.commit()
        st.success('Resultados gravados com sucesso!')
        st.rerun()

# -----------------------------------------------------------------------------
# ABA 3: CLASSIFICAÇÃO COM FILTRO POR TURMA
# -----------------------------------------------------------------------------
elif aba == '📊 Classificação por Turma & Rodada':
  st.header('🏆 Classificação do Torneio')

  with get_connection() as conn:
    df_turmas = pd.read_sql_query(
        'SELECT DISTINCT turma FROM jogadores;', conn
    )
    turmas_list = ['Todas as Turmas'] + df_turmas['turma'].tolist()

    turma_filtro = st.selectbox('Filtrar por Turma:', turmas_list)

    query = 'SELECT nome AS [Nome], turma AS [Turma], escola AS [Escola], categoria AS [Categoria], pontos AS [Pontos], rating_atual AS [Rating Elo] FROM jogadores'
    if turma_filtro != 'Todas as Turmas':
      query += f" WHERE turma = '{turma_filtro}'"
    query += ' ORDER BY pontos DESC, rating_atual DESC;'

    df_classificacao = pd.read_sql_query(query, conn)
    df_classificacao.index = range(1, len(df_classificacao) + 1)

  st.dataframe(df_classificacao, use_container_width=True)

  csv = df_classificacao.to_csv(index=True).encode('utf-8')
  st.download_button(
      label='📥 Baixar Tabela em CSV',
      data=csv,
      file_name=f'classificacao_{turma_filtro.lower().replace(" ", "_")}.csv',
      mime='text/csv',
  )

# -----------------------------------------------------------------------------
# ABA 4: CRONÔMETRO REGRISSIVO COM APITO SONORO
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