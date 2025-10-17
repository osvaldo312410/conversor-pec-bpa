from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, Response, url_for
import os
import threading
import uuid
import subprocess
import shutil
import sqlite3
import psycopg2
import json
import io
import csv
import time
import threading
import webview
from datetime import datetime, timedelta
from dbfread import DBF
from ftplib import FTP, error_perm
from functools import wraps
from psycopg2 import OperationalError
from pathlib import Path
import platform

app = Flask(__name__)
app.secret_key = 'ajnfd27efgh26effjdi)@43yrhf#@!gdwygs@*¨n'

# Config
FTP_HOST = "arpoador.datasus.gov.br"
FTP_DIR = "/siasus/sia"
BDSIA_FOLDER = os.path.join(app.root_path, "bdsia")
SQLITE_DB_PATH = os.path.join(app.root_path, "bdsia.sqlite")
os.makedirs(BDSIA_FOLDER, exist_ok=True)

# Configuração de Bloqueio por Data
DATA_BLOQUEIO = datetime(2026, 12, 31, 0, 0, 0)  # Data e hora do bloqueio
BLOQUEIO_ATIVADO = True  # Altere para False para desativar o bloqueio

# Shared progress store (thread-safe access com lock)
progress_store = {}
progress_lock = threading.Lock()

def verificar_bloqueio():
    """Verifica se o sistema deve ser bloqueado baseado na data"""
    if not BLOQUEIO_ATIVADO:
        return False
    
    data_atual = datetime.now()
    return data_atual > DATA_BLOQUEIO

def bloqueio_required(f):
    """Decorator para bloquear rotas após a data limite"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if verificar_bloqueio():
            return render_template('bloqueio.html', 
                data_limite=DATA_BLOQUEIO.strftime('%d/%m/%Y')),403
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    """Conecta ao banco SQLite"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa o banco de dados criando a tabela tb_fat_prod se não existir"""
    conn = get_db()
    cursor = conn.cursor()
    
    tabela_prod = """
    CREATE TABLE IF NOT EXISTS tb_fat_prod (
        ficha TEXT,
        prd_ident TEXT,
        prd_cnes TEXT,
        prd_cmp TEXT,
        prd_cnsmed TEXT,
        prd_cbo TEXT,
        prd_dtaten TEXT,
        prd_flh TEXT,
        prd_seq TEXT,
        prd_pa TEXT,
        prd_cnspac TEXT,
        prd_sexo TEXT,
        prd_ibge TEXT,
        prd_cid TEXT,
        prd_idade TEXT,
        prd_qt TEXT,
        prd_caten TEXT,
        prd_naut TEXT,
        prd_org TEXT,
        prd_nmpac TEXT,
        prd_dtnasc TEXT,
        raca_cor TEXT,
        etnia TEXT,
        nacionalidade TEXT,
        prd_srv TEXT,
        prd_clf TEXT,
        prd_equipe_seq TEXT,
        prd_equipe_area TEXT,
        prd_cnpj TEXT,
        prd_cep_pcnte TEXT,
        prd_lograd_pcnte TEXT,
        prd_end_pcnte TEXT,
        prd_compl_pcnte TEXT,
        prd_num_pcnte TEXT,
        prd_bairro_pcnte TEXT,
        prd_ddtel_pcnte TEXT,
        prd_email_pcnte TEXT,
        ine TEXT,
        prd_fim TEXT,
        prd_cpfpac TEXT,
        rn INTEGER
    );
    """

    tabela_config_procedimentos = """
    CREATE TABLE IF NOT EXISTS tb_config_proced (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proced TEXT NOT NULL,
        cid TEXT,
        servico TEXT,
        classificacao TEXT,
        UNIQUE(proced)
    );
    """

    tabela_dados_municipio = """
    CREATE TABLE IF NOT EXISTS tb_dados_municipio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no_municipio TEXT, 
        ds_sigla TEXT, 
        nu_cnes TEXT, 
        nu_cnpj TEXT,
        co_ibge TEXT
    );
    """
    
    cursor.execute(tabela_prod)
    cursor.execute(tabela_config_procedimentos)
    cursor.execute(tabela_dados_municipio)
    conn.commit()
    conn.close()

# Rota para verificar status do bloqueio (útil para o frontend)
@app.route('/api/status-bloqueio')
def status_bloqueio():
    bloqueado = verificar_bloqueio()
    dias_restantes = (DATA_BLOQUEIO - datetime.now()).days if not bloqueado else 0
    
    return jsonify({
        'bloqueado': bloqueado,
        'data_limite': DATA_BLOQUEIO.strftime('%d/%m/%Y'),
        'dias_restantes': max(0, dias_restantes),
        'bloqueio_ativado': BLOQUEIO_ATIVADO
    })

# Rota especial para o template de bloqueio (não bloqueada)
@app.route('/bloqueio')
def pagina_bloqueio():
    if verificar_bloqueio():
        return render_template('bloqueio.html', 
                             data_limite=DATA_BLOQUEIO.strftime('%d/%m/%Y'))
    else:
        return redirect(url_for('inicio'))

@app.route('/')
@bloqueio_required
def inicio():
    return render_template('inicio.html')

@app.route('/index')
@bloqueio_required
def index():
    """Rota principal com paginação e filtro - versão tolerante a erros"""
    init_db()  # Garante que as tabelas básicas existem
    
    # Obter número da página e filtro da query string
    page = request.args.get('page', 1, type=int)
    filtro = request.args.get('filtro', 'todos')  # 'todos', 'valido', 'invalido'
    resultados_por_pagina = 500
    
    offset = (page - 1) * resultados_por_pagina
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Inicializar variáveis com valores padrão
    prod = []
    proced_cbo_list = []
    proced_filter = []
    proced_cid_dict = {}
    proced_srv_dict = {}
    municipio = []
    total_registros = 0
    
    try:
        # Buscar lista de proced válidos (com tratamento de erro para cada query)
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='S_PACBO'")
            if cursor.fetchone():
                cursor2 = conn.cursor()
                cursor2.execute("""
                    select * from (
                        select 
                            sp2.pa_id || '' || sp2.PA_DV as proced,
                            sp.PACBO_CBO as cbo,
                            sp.PACBO_CMP as cmp,
                            row_number() over(
                                partition by sp2.pa_id
                                order by cast(sp.PACBO_CMP as integer) desc
                            ) rn
                        from S_PACBO sp
                        left join S_PROCED sp2 on sp2.pa_id = sp.PACBO_PA
                    ) sub 
                    where sub.rn = 1
                """)
                proced_cbo = cursor2.fetchall()
                proced_cbo_list = [row[0] for row in proced_cbo] if proced_cbo else []
                proced_filter = [row[1] for row in proced_cbo] if proced_cbo else []
                cursor2.close()
        except sqlite3.OperationalError as e:
            print(f"Tabela S_PACBO não disponível: {e}")
            proced_cbo_list = []
            proced_filter = []

        # Buscar procedimentos com CID
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='S_PACID'")
            if cursor.fetchone():
                cursor3 = conn.cursor()
                cursor3.execute("""
                    select * from (
                        select 
                            sp.PACID_PA as proced,
                            sp.PACID_CID as cid,
                            row_number() over(
                                partition by sp.PACID_PA, sp.PACID_CID
                                order by cast(pacid_cmp as integer) desc
                            ) rn
                        from S_PACID sp
                    ) sub 
                    where sub.rn = 1
                """)
                proced_cid_rows = cursor3.fetchall()
                cursor3.close()

                # Cria um dicionário: {proced: [cid1, cid2, ...]}
                proced_cid_dict = {}
                for row in proced_cid_rows:
                    proced = row[0]
                    cid = row[1]
                    if proced in proced_cid_dict:
                        proced_cid_dict[proced].append(cid)
                    else:
                        proced_cid_dict[proced] = [cid]
        except sqlite3.OperationalError as e:
            print(f"Tabela S_PACID não disponível: {e}")
            proced_cid_dict = {}

        # Buscar procedimentos com serviços
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='S_PASRV'")
            if cursor.fetchone():
                cursor4 = conn.cursor()
                cursor4.execute("""
                    select * from (
                        select 
                            sp2.pa_id || '' || sp2.PA_DV as proced,
                            sp.PASRV_SRV as servico,
                            sp.PASRV_CSF as classificacao,
                            row_number() over(
                                partition by sp2.pa_id
                                order by cast(sp.PASRV_CMP as integer) desc
                            ) rn
                        from S_PASRV sp 
                        left join S_PROCED sp2 on sp2.pa_id = sp.PASRV_PA
                    ) sub
                    where sub.rn = 1
                """)
                proced_srv_rows = cursor4.fetchall()
                cursor4.close()

                # Cria um dicionário: {proced: {'srv': [], 'clf': []}}
                proced_srv_dict = {}
                for row in proced_srv_rows:
                    proced = row[0]
                    srv = row[1]
                    clf = row[2]
                    
                    if proced in proced_srv_dict:
                        proced_srv_dict[proced]['srv'].append(srv)
                        proced_srv_dict[proced]['clf'].append(clf)
                    else:
                        proced_srv_dict[proced] = {'srv': [srv], 'clf': [clf]}
        except sqlite3.OperationalError as e:
            print(f"Tabela S_PASRV não disponível: {e}")
            proced_srv_dict = {}

        # Buscar dados de município
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tb_dados_municipio'")
            if cursor.fetchone():
                cursor5 = conn.cursor()
                cursor5.execute("SELECT * FROM tb_dados_municipio")
                municipio = cursor5.fetchall()
                cursor5.close()
        except sqlite3.OperationalError as e:
            print(f"Tabela tb_dados_municipio não disponível: {e}")
            municipio = []

        # Verificar se a tabela principal existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tb_fat_prod'")
        if cursor.fetchone():
            # Montar SQL base
            sql = """
                SELECT 
                    *,
                    tcp.cid,
                    tcp.servico,
                    tcp.classificacao
                FROM 
                tb_fat_prod tfp
                left join tb_config_proced tcp 
                on tcp.proced = tfp.prd_pa
            """
            params = []

            if filtro == "valido" and proced_cbo_list:
                placeholders = ",".join(["?"] * len(proced_cbo_list))
                sql += f" WHERE tfp.prd_pa IN ({placeholders})"
                params.extend(proced_cbo_list)
            elif filtro == "invalido" and proced_cbo_list:
                placeholders = ",".join(["?"] * len(proced_cbo_list))
                sql += f" WHERE tfp.prd_pa NOT IN ({placeholders})"
                params.extend(proced_cbo_list)

            # Paginação
            sql += " LIMIT ? OFFSET ?"
            params.extend([resultados_por_pagina, offset])

            cursor.execute(sql, params)
            prod = cursor.fetchall()

            # Contar total de registros
            sql_count = "SELECT COUNT(*) FROM tb_fat_prod tfp"
            params_count = []

            if filtro == "valido" and proced_cbo_list:
                placeholders = ",".join(["?"] * len(proced_cbo_list))
                sql_count += f" WHERE tfp.prd_pa IN ({placeholders})"
                params_count.extend(proced_cbo_list)
            elif filtro == "invalido" and proced_cbo_list:
                placeholders = ",".join(["?"] * len(proced_cbo_list))
                sql_count += f" WHERE tfp.prd_pa NOT IN ({placeholders})"
                params_count.extend(proced_cbo_list)

            cursor.execute(sql_count, params_count)
            total_registros = cursor.fetchone()[0] or 0
        else:
            print("Tabela tb_fat_prod não existe ainda")
            prod = []
            total_registros = 0

    except sqlite3.OperationalError as e:
        print(f"Erro geral na consulta: {e}")
        prod = []
        total_registros = 0
        
        if page > 1:
            return redirect(url_for('index', page=1))
    
    finally:
        conn.close()
    
    # Calcular total de páginas
    total_paginas = max(1, (total_registros + resultados_por_pagina - 1) // resultados_por_pagina)

    start_page = max(1, page - 4)
    end_page = min(total_paginas, start_page + 9)
    if end_page - start_page < 9 and start_page > 1:
        start_page = max(1, end_page - 9)

    return render_template(
        'index.html', 
        prod=prod,
        page=page,
        total_paginas=total_paginas,
        start_page=start_page,
        end_page=end_page,
        proced_cbo_list=proced_cbo_list,
        filtro=filtro,
        proced_filter=proced_filter,
        proced_cid_dict=proced_cid_dict,
        proced_srv_dict=proced_srv_dict,
        municipio=municipio
    )


# Adicione esta função para fechar conexões do banco
@app.teardown_appcontext
def close_connection(exception):
    conn = getattr(app, '_database', None)
    if conn is not None:
        conn.close()


def _safe_update_progress(download_id, **kwargs):
    """Atualiza progress_store de forma thread-safe."""
    with progress_lock:
        entry = progress_store.setdefault(download_id, {
            "status": "started",    # started, running, done, error
            "downloaded": 0,
            "total": 0,
            "filename": None,
            "file_path": None,
            "error": None
        })
        entry.update(kwargs)

# =============================================================================================================
# Rota que baixa bdsia 

@app.route('/download_bdsia')
@bloqueio_required
def download_bdsia_page():
    """Página dedicada para download do BDSIA"""
    return render_template('download_bdsia.html')

def find_remote_file_for_competencia(competencia):
    """
    Conecta ao FTP e procura arquivos que comecem com 'BDSIA{competencia}' e terminem com .exe.
    Retorna (filename, size) do arquivo escolhido, ou (None, 0) se não encontrar.
    """
    ftp = FTP(FTP_HOST, timeout=30)
    ftp.login()  # anonymous
    ftp.cwd(FTP_DIR)
    candidates = []

    try:
        for name, facts in ftp.mlsd():
            if name.startswith(f"BDSIA{competencia}") and name.lower().endswith(".exe"):
                size = int(facts.get("size", 0)) if facts.get("size") else 0
                modify = facts.get("modify")
                candidates.append({"name": name, "size": size, "modify": modify})
    except Exception:
        try:
            for name in ftp.nlst():
                if name.startswith(f"BDSIA{competencia}") and name.lower().endswith(".exe"):
                    sz = 0
                    try:
                        sz = ftp.size(name) or 0
                    except Exception:
                        sz = 0
                    candidates.append({"name": name, "size": sz, "modify": None})
        except Exception:
            pass

    try:
        ftp.quit()
    except Exception:
        pass

    if not candidates:
        return None, 0

    candidates.sort(key=lambda x: (x.get("modify") or "", x.get("size") or 0), reverse=True)
    chosen = candidates[0]
    return chosen["name"], chosen["size"]


def download_worker(filename, download_id):
    """Thread worker: baixa o arquivo do FTP e atualiza progress_store via _safe_update_progress."""
    try:
        _safe_update_progress(download_id, status="running", filename=filename, downloaded=0)

        ftp = FTP(FTP_HOST, timeout=60)
        ftp.login()
        ftp.cwd(FTP_DIR)

        total = 0
        try:
            total = ftp.size(filename) or 0
        except Exception:
            total = 0
        _safe_update_progress(download_id, total=total)

        local_path = os.path.join(BDSIA_FOLDER, filename)

        with open(local_path, "wb") as f:
            def callback(data):
                f.write(data)
                with progress_lock:
                    progress_store[download_id]["downloaded"] += len(data)

            ftp.retrbinary(f"RETR {filename}", callback, blocksize=8192)

        try:
            ftp.quit()
        except Exception:
            pass

        _safe_update_progress(download_id, status="done", file_path=local_path,
                              downloaded=progress_store[download_id].get("downloaded", 0))

        # 🔹 Adiciona um pequeno atraso antes da execução
        time.sleep(2)
        
        # 🔹 Executa o arquivo baixado dentro da pasta /bdsia
        try:
            # Adiciona mensagem informativa no progresso
            _safe_update_progress(download_id, status="installing", 
                                 message="Iniciando instalação do BDSIA...")
            
            subprocess.Popen([local_path], cwd=BDSIA_FOLDER, shell=True)
            
            # Atualiza status para indicar que a instalação foi iniciada
            _safe_update_progress(download_id, status="installation_started",
                                 message="Instalação iniciada. Aguarde a conclusão antes de converter.")
            
        except Exception as e:
            _safe_update_progress(download_id, status="error", error=f"Falha ao executar: {e}")

    except Exception as e:
        _safe_update_progress(download_id, status="error", error=str(e))


@app.route("/start_download_bdsia", methods=["POST"])
@bloqueio_required
def start_download_bdsia():
    data = request.get_json() or {}
    competencia = data.get("competencia")
    if not competencia:
        return jsonify({"error": "Competência não informada (ex: 202508)"}), 400

    # 🔹 Limpar pasta antes de novo download
    for nome in os.listdir(BDSIA_FOLDER):
        caminho = os.path.join(BDSIA_FOLDER, nome)
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
            elif os.path.isdir(caminho):
                shutil.rmtree(caminho)
        except Exception:
            pass

    filename, size = find_remote_file_for_competencia(competencia)
    if not filename:
        return jsonify({"error": f"Nenhum arquivo encontrado para competência {competencia}"}), 404

    download_id = str(uuid.uuid4())
    _safe_update_progress(download_id, status="queued", filename=filename, total=size, downloaded=0)

    t = threading.Thread(target=download_worker, args=(filename, download_id), daemon=True)
    t.start()

    return jsonify({"download_id": download_id, "filename": filename, "total": size})


@app.route("/download_progress/<download_id>", methods=["GET"])
@bloqueio_required
def download_progress(download_id):
    with progress_lock:
        entry = progress_store.get(download_id)
        if not entry:
            return jsonify({"error": "download_id não encontrado"}), 404
        total = entry.get("total", 0) or 0
        downloaded = entry.get("downloaded", 0) or 0
        if total:
            percent = int(downloaded / total * 100)
            if percent > 100:
                percent = 100
        else:
            percent = None

        return jsonify({
            "status": entry.get("status"),
            "filename": entry.get("filename"),
            "downloaded": downloaded,
            "total": total,
            "percent": percent,
            "file_path": entry.get("file_path"),
            "error": entry.get("error")
        })


@app.route('/bdsia/<path:filename>')
@bloqueio_required
def serve_bdsia(filename):
    return send_from_directory(BDSIA_FOLDER, filename, as_attachment=True)

def convert_worker(convert_id):
    """Converte os arquivos .DBF da pasta BDSIA em tabelas SQLite na raiz do projeto."""
    try:
        print("Iniciando conversão...")
        files = [f for f in os.listdir(BDSIA_FOLDER) if f.lower().endswith(".dbf")]
        print(f"Arquivos DBF encontrados: {files}")
        total_files = len(files)
        if total_files == 0:
            _safe_update_progress(convert_id, status="error", error="Nenhum arquivo .DBF encontrado")
            print("Nenhum DBF encontrado. Conversão abortada.")
            return

        _safe_update_progress(convert_id, status="running", downloaded=0, total=total_files)

        # Cria/abre o banco SQLite na raiz
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cur = conn.cursor()
        processed = 0

        for f in files:
            table_name = os.path.splitext(f)[0]
            dbf_path = os.path.join(BDSIA_FOLDER, f)

            try:
                table = DBF(dbf_path, encoding="latin-1")
                columns = [f'"{field.name}" TEXT' for field in table.fields]

                cur.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                cur.execute(f'CREATE TABLE "{table_name}" ({",".join(columns)})')

                col_names = [f'"{field.name}"' for field in table.fields]
                placeholders = ",".join("?" for _ in table.fields)
                insert_sql = f'INSERT INTO "{table_name}" ({",".join(col_names)}) VALUES ({placeholders})'

                for record in table:
                    values = [str(record[field.name]) if record[field.name] is not None else None for field in table.fields]
                    cur.execute(insert_sql, values)

                conn.commit()
                print(f"Tabela {table_name} criada com {len(table)} registros.")

            except Exception as e:
                print(f"Erro processando {f}: {e}")
                continue

            processed += 1
            percent = int(processed / total_files * 100)
            _safe_update_progress(convert_id, downloaded=processed, total=total_files, percent=percent)

        conn.close()
        _safe_update_progress(convert_id, status="done", file_path=SQLITE_DB_PATH, downloaded=total_files, total=total_files)
        print(f"Conversão concluída. Banco criado: {SQLITE_DB_PATH}")

    except Exception as e:
        _safe_update_progress(convert_id, status="error", error=str(e))
        print(f"Erro na conversão: {e}")

@app.route("/check_files_status")
@bloqueio_required
def check_files_status():
    """Verifica quantos arquivos .DBF estão disponíveis para conversão"""
    try:
        # Lista todos os arquivos .DBF na pasta BDSIA
        dbf_files = [f for f in os.listdir(BDSIA_FOLDER) if f.lower().endswith(".dbf")]
        files_available = len(dbf_files)
        
        # Define o número total esperado de arquivos (normalmente 24)
        total_files_expected = 24
        
        # Verifica se todos os arquivos esperados estão disponíveis
        ready_for_conversion = files_available >= total_files_expected
        
        return jsonify({
            "files_available": files_available,
            "total_files": total_files_expected,
            "ready_for_conversion": ready_for_conversion,
            "files": dbf_files  # Opcional: lista os nomes dos arquivos encontrados
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Erro ao verificar arquivos: {str(e)}",
            "files_available": 0,
            "total_files": 24,
            "ready_for_conversion": False
        }), 500

@app.route("/check_installation")
@bloqueio_required
def check_installation():
    """Verifica se o BDSIA foi instalado (se existem arquivos .DBF)"""
    try:
        dbf_files = [f for f in os.listdir(BDSIA_FOLDER) if f.lower().endswith(".dbf")]
        return jsonify({
            "installed": len(dbf_files) > 0, 
            "dbf_count": len(dbf_files),
            "files": dbf_files
        })
    except Exception as e:
        return jsonify({"installed": False, "error": str(e)})
        

@app.route("/start_convert_bdsia", methods=["POST"])
@bloqueio_required
def start_convert_bdsia():
    download_id = str(uuid.uuid4())
    _safe_update_progress(download_id, status="queued", downloaded=0, total=0)

    t = threading.Thread(target=convert_worker, args=(download_id,), daemon=True)
    t.start()

    return jsonify({"download_id": download_id, "filename": "bdsia.sqlite"})

#========================================================================================================
# Rota de conexão com o pec 

@app.route('/conecta_pec')
@bloqueio_required
def conecta_pec():
    return render_template('conecta_pec.html')

#========================================================================================================
# Funções de Conexão

# Função para carregar configurações
def load_config():
    config_file = 'config.json'
    default_config = {
        'host': '',
        'database': '',
        'user': '',
        'password': '',
        'port': ''
    }
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            # Se o arquivo não existir, cria com configurações padrão
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")
        return default_config

# Função para salvar configurações
def save_config(config):
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")
        return False

# Função para testar conexão com o PostgreSQL
def test_postgres_connection(config):
    try:
        conn = psycopg2.connect(
            host=config['host'],
            database=config['database'],
            user=config['user'],
            password=config['password'],
            port=config['port']
        )
        conn.close()
        return True, "Conexão bem-sucedida!"
    except OperationalError as e:
        return False, f"Erro de conexão: {e}"
    except Exception as e:
        return False, f"Erro inesperado: {e}"

# Decorator para verificar se é JSON
def json_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.is_json:
            return f(*args, **kwargs)
        else:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
    return decorated_function

@app.route('/db_config', methods=['GET'])
@bloqueio_required
def config_page():
    config = load_config()
    return render_template('config_page.html', config=config)

@app.route('/db_config/save', methods=['POST'])
@bloqueio_required
@json_request
def save_config_api():
    try:
        data = request.get_json()
        
        # Validação básica dos dados
        required_fields = ['host', 'database', 'user', 'password', 'port']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Campo {field} é obrigatório'}), 400
        
        # Converte port para string (se for número)
        data['port'] = str(data['port'])
        
        if save_config(data):
            return jsonify({'message': 'Configurações salvas com sucesso!', 'config': data})
        else:
            return jsonify({'error': 'Erro ao salvar configurações'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@app.route('/db_config/get', methods=['GET'])
@bloqueio_required
def get_config():
    config = load_config()
    return jsonify(config)

@app.route('/db_config/test', methods=['POST'])
@bloqueio_required
@json_request
def test_connection():
    try:
        data = request.get_json()
        
        # Validação básica dos dados
        required_fields = ['host', 'database', 'user', 'password', 'port']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Campo {field} é obrigatório'}), 400
        
        # Testar a conexão
        success, message = test_postgres_connection(data)
        
        if success:
            return jsonify({'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500
    
#==========================================================================================================
def get_postgres_connection():
    """Conecta ao banco PostgreSQL usando as configurações salvas"""
    config = load_config()
    
    try:
        conn = psycopg2.connect(
            host=config['host'],
            database=config['database'],
            user=config['user'],
            password=config['password'],
            port=config['port']
        )
        return conn
    except OperationalError as e:
        print(f"Erro de conexão com PostgreSQL: {e}")
        raise
    except Exception as e:
        print(f"Erro inesperado ao conectar com PostgreSQL: {e}")
        raise

 #============================================================================================
 # Rota que processa dados da produção PEC   

@app.route('/processar_producao', methods=['POST'])
@bloqueio_required
def processar_producao():
    try:
        data = request.get_json()
        competencia = data.get('competencia') if data else None
        cnes = data.get('cnes') if data else None

        conn_postgres = None
        conn_sqlite = None
        
        try:
            # Conectar ao PostgreSQL
            print("Conectando ao PostgreSQL...")
            with progress_lock:
                progress_store['producao'] = {'progress': 10, 'message': 'Conectando ao PostgreSQL...'}
            
            conn_postgres = get_postgres_connection()
            cursor_postgres = conn_postgres.cursor()
            print("Conexão PostgreSQL estabelecida")
            
            # Conectar ao SQLite
            print("Conectando ao SQLite...")
            conn_sqlite = get_db()
            cursor_sqlite = conn_sqlite.cursor()
            print("Conexão SQLite estabelecida")
            
            # Query completa do PostgreSQL
            print("Executando query no PostgreSQL...")
            query = f"""
            with proced as (
            select * from (
            select distinct * from (
            select 
                '03'::text as ident,
                tfpa.co_seq_fat_proced_atend ficha,
                tfpa.co_fat_cidadao_pec cod,
                cast(tfpa.dt_final_atendimento as date) dt_atend,
                unnest(string_to_array(tfpa.ds_filtro_procedimento, '|')) sigtap,
                null::text as cid,
                tdp.nu_cns cns_prof,
                tdc.nu_cbo cbo,
                tdus.nu_cnes cnes,
                case 
                    when tde.nu_ine = '-' then null::text else tde.nu_ine
                end as ine
            from tb_fat_proced_atend tfpa 
            left join tb_fat_atendimento_individual tfai 
            on tfai.nu_uuid_ficha = tfpa.nu_uuid_ficha
            left join tb_dim_profissional tdp 
            on tdp.co_seq_dim_profissional = tfpa.co_dim_profissional 
            left join tb_dim_cbo tdc 
            on tdc.co_seq_dim_cbo = tfpa.co_dim_cbo 
            left join tb_dim_unidade_saude tdus 
            on tdus.co_seq_dim_unidade_saude = tfpa.co_dim_unidade_saude 
            left join tb_dim_equipe tde 
            on tde.co_seq_dim_equipe = tfpa.co_dim_equipe) sub 
            where sub.sigtap <> '' 
            and sub.sigtap not like 'ABPG%' 
            and sub.sigtap not like 'ABEX%'

            union all 

            select distinct * from (
            select 
                '03'::text as ident,
                tfpa.co_seq_fat_proced_atend ficha,
                tfpa.co_fat_cidadao_pec cod,
                cast(tfpa.dt_final_atendimento as date) dt_atend,
                null::text as sigtap,
                unnest(string_to_array(tfai.ds_filtro_cids, '|')) cid,
                tdp.nu_cns cns_prof,
                tdc.nu_cbo cbo,
                tdus.nu_cnes cnes,
                case 
                    when tde.nu_ine = '-' then null::text else tde.nu_ine
                end as ine
            from tb_fat_proced_atend tfpa 
            left join tb_fat_atendimento_individual tfai 
            on tfai.nu_uuid_ficha = tfpa.nu_uuid_ficha
            left join tb_dim_profissional tdp 
            on tdp.co_seq_dim_profissional = tfpa.co_dim_profissional 
            left join tb_dim_cbo tdc 
            on tdc.co_seq_dim_cbo = tfpa.co_dim_cbo 
            left join tb_dim_unidade_saude tdus 
            on tdus.co_seq_dim_unidade_saude = tfpa.co_dim_unidade_saude 
            left join tb_dim_equipe tde 
            on tde.co_seq_dim_equipe = tfpa.co_dim_equipe) sub 
            where sub.cid <> '') fin 
            where fin.cod is not null 
            and fin.dt_atend is not null 
            and to_char(fin.dt_atend, 'YYYYMM') = '{competencia}'
            order by fin.dt_atend, fin.cnes asc
            ),
            cidadao as (
            select 
                tfcp.co_seq_fat_cidadao_pec cod,
                tfcp.no_cidadao nome,
                to_date(tfcp.co_dim_tempo_nascimento::text, 'YYYYMMDD') dt_nasc,
                lpad(extract(year from age(to_date(tfcp.co_dim_tempo_nascimento::text, 'YYYYMMDD')))::text, 3, '0') idade,
                tfcp.nu_cns cns,
                tfcp.nu_cpf_cidadao cpf,
                case 
                    when tfcp.co_dim_sexo = 1 then 'M' else 'F'
                end as sexo,
                case 
                    when tdrc.nu_ms = '-' then '99'
                    else tdrc.nu_ms
                end as raca_cor,
                lpad(case 
                    when tde.nu_identificador = '-' then null::text
                    else tde.nu_identificador
                end::text, 4, '0') etnia,
                lpad(case 
                    when tdn.co_nacionalidade = '-' then null::text
                    else tdn.co_nacionalidade
                end::text, 3, '0') nacionalidade,
                left(tfci.no_email, 40) email
            from tb_fat_cidadao_pec tfcp
            left join tb_fat_cad_individual tfci 
            on tfci.co_fat_cidadao_pec = tfcp.co_seq_fat_cidadao_pec
            left join tb_dim_raca_cor tdrc 
            on tdrc.co_seq_dim_raca_cor = tfci.co_dim_raca_cor
            left join tb_dim_etnia tde 
            on tde.co_seq_dim_etnia = tfci.co_dim_etnia
            left join tb_dim_nacionalidade tdn  
            on tdn.co_seq_dim_nacionalidade = tfci.co_dim_nacionalidade),
            cad_domiciliar as(
            select * from (
            WITH domicilio AS (
                SELECT 
                    tcd.co_unico_domicilio AS ficha,
                    tcd.tp_logradouro,
                    tcd.no_logradouro AS rua,
                    tcd.nu_domicilio AS numero,
                    tcd.ds_complemento AS complemento, 
                    tcd.ds_cep AS cep,
                    tcd.no_bairro as bairro,
                    tcd.nu_fone_referencia,
                    tcd.nu_fone_residencia,
                    tcd.nu_micro_area AS ma,
                    UPPER(tdp.no_profissional) AS prof,
                    tcd.nu_cnes,
                    tcd.nu_ine
                FROM tb_cds_domicilio tcd 
                LEFT JOIN tb_dim_profissional tdp ON tdp.nu_cns = tcd.nu_cns
            ), 
            dependente AS (
                SELECT
                    tfci.co_fat_cidadao_pec_responsvl AS cod_resp,
                    tfci.co_fat_cidadao_pec AS cod_dep,
                    tfcp.no_cidadao AS no_dep
                FROM tb_fat_cad_individual tfci
                JOIN tb_fat_cidadao_pec tfcp 
                    ON tfcp.co_seq_fat_cidadao_pec = tfci.co_fat_cidadao_pec
                JOIN tb_fat_cidadao_territorio tfct 
                    ON tfct.co_fat_cidadao_pec = tfci.co_fat_cidadao_pec
                JOIN tb_cds_cad_individual tcci 
                    ON tcci.nu_cpf_cidadao = tfci.nu_cpf_cidadao 
                WHERE tfct.st_mudou_se = 0
            ),
            ultimas_fichas AS (
                SELECT
                    tfft.nu_uuid_ficha_origem AS ficha,
                    tfft.co_fat_cidadao_pec AS cod_resp,
                    tfcp.nu_cpf_cidadao AS cpf_resp,
                    TO_CHAR(to_date(tfft.co_dim_tempo_fcd::text, 'YYYYMMDD'), 'DD/MM/YYYY') AS dt_ultima_atualizacao,
                    ROW_NUMBER() OVER(
                        PARTITION BY tfft.co_fat_cidadao_territorio 
                        ORDER BY tfft.co_dim_tempo_fcd DESC
                    ) AS rn
                FROM tb_fat_familia_territorio tfft
                JOIN tb_fat_cidadao_pec tfcp 
                    ON tfcp.co_seq_fat_cidadao_pec = tfft.co_fat_cidadao_pec
            )
            SELECT DISTINCT
                uf.ficha,
                uf.dt_ultima_atualizacao,
                uf.cod_resp,
                d.cod_dep,
                'NÃO'::text as resp,
                d.no_dep,
                dom.tp_logradouro,
                dom.rua,
                dom.numero,
                dom.complemento, 
                dom.cep,
                dom.bairro,
                dom.nu_fone_referencia,
                dom.nu_fone_residencia,
                dom.ma,
                dom.prof,
                dom.nu_cnes cnes,
                dom.nu_ine ine
            FROM ultimas_fichas uf
            JOIN dependente d ON d.cod_resp = uf.cod_resp 
            LEFT JOIN domicilio dom ON dom.ficha = uf.ficha
            WHERE uf.rn = 1

            UNION ALL 

            SELECT DISTINCT
                uf.ficha,
                uf.dt_ultima_atualizacao,
                uf.cod_resp,
                uf.cod_resp AS cod_dep,
                'SIM'::text as resp,
                tfcp.no_cidadao AS no_dep,
                dom.tp_logradouro,
                dom.rua,
                dom.numero,
                dom.complemento, 
                dom.cep,
                dom.bairro,
                dom.nu_fone_referencia,
                dom.nu_fone_residencia,
                dom.ma,
                dom.prof,
                dom.nu_cnes cnes,
                dom.nu_ine ine
            FROM ultimas_fichas uf
            JOIN tb_fat_cidadao_pec tfcp ON tfcp.co_seq_fat_cidadao_pec = uf.cod_resp 
            LEFT JOIN domicilio dom ON dom.ficha = uf.ficha
            WHERE uf.rn = 1) fin           
            )
            select  
                f.ficha,
                f.prd_ident,
                f.prd_cnes,
                f.prd_cmp,
                f.prd_cnsmed,
                f.prd_cbo,
                f.prd_dtaten,
                lpad((floor((f.sequencia_global - 1) / 99) + 1)::text, 3, '0') as prd_flh,
                lpad(((f.sequencia_global - 1) % 99 + 1)::text, 2, '0') as prd_seq,
                f.prd_pa,
                f.prd_cnspac,
                f.prd_sexo,
                f.prd_ibge,
                f.prd_cid,
                f.prd_idade,
                f.prd_qt,
                f.prd_caten,
                f.prd_naut,
                f.prd_org,
                f.prd_nmpac,
                f.prd_dtnasc,
                f.raca_cor,
                f.etnia,
                f.nacionalidade,
                f.prd_srv, 
                f.prd_clf, 
                f.prd_equipe_seq, 
                f.prd_equipe_area, 
                f.prd_cnpj,
                f.prd_cep_pcnte,
                f.prd_lograd_pcnte,
                f.prd_end_pcnte,
                f.prd_compl_pcnte,
                f.prd_num_pcnte,
                f.prd_bairro_pcnte,
                f.prd_ddtel_pcnte,
                f.prd_email_pcnte,
                f.ine,
                f.prd_fim,
                f.prd_cpfpac,
                f.rn
            from (
            select 
                fin.ficha,
                fin.prd_ident,
                fin.prd_cnes,
                fin.prd_cmp,
                fin.prd_cnsmed,
                fin.prd_cbo,
                fin.prd_dtaten,
                '' as prd_flh,
                '' as prd_seq,
                fin.prd_pa,
                fin.prd_cnspac,
                fin.prd_sexo,
                fin.prd_ibge,
                fin.prd_cid,
                fin.prd_idade,
                fin.prd_qt,
                fin.prd_caten,
                fin.prd_naut,
                fin.prd_org,
                fin.prd_nmpac,
                fin.prd_dtnasc,
                fin.raca_cor,
                fin.etnia,
                '010' as nacionalidade,
                fin.prd_srv, 
                fin.prd_clf, 
                fin.prd_equipe_seq, 
                fin.prd_equipe_area, 
                fin.prd_cnpj,
                fin.prd_cep_pcnte,
                '010' as prd_lograd_pcnte,
                fin.prd_end_pcnte,
                fin.prd_compl_pcnte,
                fin.prd_num_pcnte,
                fin.prd_bairro_pcnte,
                fin.prd_ddtel_pcnte,
                fin.prd_email_pcnte,
                fin.ine,
                fin.prd_fim,
                fin.prd_cpfpac,
                fin.rn,
                row_number() over (
                    partition by fin.prd_ident
                    order by fin.prd_dtaten, fin.prd_cnes asc
                ) as sequencia_global
            from (
            select 
                p.ficha,
                p.ident prd_ident,
                p.cnes prd_cnes,
                to_char(p.dt_atend, 'YYYYMM') prd_cmp,
                p.cns_prof prd_cnsmed,
                p.cbo prd_cbo,
                to_char(p.dt_atend, 'YYYYMMDD') prd_dtaten,
                null::text as prd_flh,
                null::text as prd_seq,
                p.sigtap prd_pa,
                c.cns prd_cnspac,
                c.sexo prd_sexo,
                null::text as prd_ibge,
                p.cid prd_cid,
                c.idade prd_idade,
                '000001'::text as prd_qt,
                '01'::text as prd_caten,
                null::text as prd_naut,
                'EXT'::text as prd_org,
                left(c.nome, 40) prd_nmpac,
                to_char(c.dt_nasc, 'YYYYMMDD') prd_dtnasc,
                c.raca_cor,
                c.etnia,
                c.nacionalidade,
                null::text as prd_srv, 
                null::text as prd_clf, 
                null::text as prd_equipe_seq, 
                null::text as prd_equipe_area, 
                null::text as prd_cnpj,
                cd.cep prd_cep_pcnte,
                lpad(cd.tp_logradouro::text, 3, '0') prd_lograd_pcnte,
                left(cd.rua, 30) prd_end_pcnte,
                left(cd.complemento, 10) prd_compl_pcnte,
                left(cd.numero, 5) prd_num_pcnte,
                left(cd.bairro, 30) prd_bairro_pcnte,
                cd.nu_fone_referencia prd_ddtel_pcnte,
                ''::text prd_email_pcnte,
                p.ine,
                null::text as prd_fim,
                c.cpf prd_cpfpac,
                p.dt_atend,
                row_number()over(
                    partition by p.ficha, p.sigtap, p.cid 
                    order by p.dt_atend desc
                ) rn,
                cast(p.dt_atend as date) dt_order 
            from proced p
            left join cidadao c 
            on c.cod = p.cod
            left join cad_domiciliar cd 
            on cd.cod_dep = p.cod
            where (p.cnes = '{cnes}' or '{cnes}' is null or '{cnes}' = '')
            ) fin 
            where fin.rn = 1 
            and fin.prd_pa is not null
            and fin.prd_nmpac is not null
            order by fin.dt_order , fin.prd_cnes asc) as f
            """
            
            with progress_lock:
                progress_store['producao'] = {'progress': 30, 'message': 'Executando consulta no PostgreSQL...'}        
            cursor_postgres.execute(query)
            rows = cursor_postgres.fetchall()
            print(f"Consulta executada. {len(rows)} registros encontrados.")
            total_rows = len(rows)
            
            if total_rows == 0:
                print("Nenhum dado encontrado para a competência.")
                with progress_lock:
                    progress_store['producao'] = {'progress': 100, 'message': 'Nenhum dado encontrado para a competência.', 'error': True}
                return jsonify({'status': 'error', 'message': 'Nenhum dado encontrado para a competência.'}), 400
            
            with progress_lock:
                progress_store['producao'] = {'progress': 50, 'message': f'Consulta concluída. {total_rows} registros encontrados. Iniciando inserção no SQLite...'}
            
            # Limpar tabela no SQLite
            print("Limpando tabela tb_fat_prod...")
            cursor_sqlite.execute("DELETE FROM tb_fat_prod")
            conn_sqlite.commit()
            print("Tabela limpa.")
            
            # Inserir dados no SQLite
            insert_query = """
            INSERT INTO tb_fat_prod (
                ficha,
                prd_ident,
                prd_cnes,
                prd_cmp,
                prd_cnsmed,
                prd_cbo,
                prd_dtaten,
                prd_flh,
                prd_seq,
                prd_pa,
                prd_cnspac,
                prd_sexo,
                prd_ibge,
                prd_cid,
                prd_idade,
                prd_qt,
                prd_caten,
                prd_naut,
                prd_org,
                prd_nmpac,
                prd_dtnasc,
                raca_cor,
                etnia,
                nacionalidade,
                prd_srv, 
                prd_clf, 
                prd_equipe_seq, 
                prd_equipe_area, 
                prd_cnpj,
                prd_cep_pcnte,
                prd_lograd_pcnte,
                prd_end_pcnte,
                prd_compl_pcnte,
                prd_num_pcnte,
                prd_bairro_pcnte,
                prd_ddtel_pcnte,
                prd_email_pcnte,
                ine,
                prd_fim,
                prd_cpfpac,
                rn 
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, ?, ?, ?, ?)
            """

            batch_size = 1000
            print(f"Iniciando inserção de {total_rows} registros...")
            
            for i in range(0, total_rows, batch_size):
                batch = rows[i:i+batch_size]
                print(f"Inserindo batch {i} a {i + len(batch)}...")
                cursor_sqlite.executemany(insert_query, batch)
                conn_sqlite.commit()
                
                with progress_lock:
                    progress_store['producao'] = {'progress': 50 + int((i + len(batch)) / total_rows * 50), 'message': f'Inseridos {i + len(batch)} de {total_rows} registros no SQLite...'}
            
            print("Inserção concluída com sucesso.")
            with progress_lock:
                progress_store['producao'] = {'progress': 100, 'message': 'Processamento concluído com sucesso.', 'error': False}
            
            return jsonify({'status': 'success', 'message': 'Processamento concluído com sucesso.'})
            
        except Exception as e:
            print(f"Erro durante o processamento: {str(e)}")
            print(f"Tipo do erro: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            
            with progress_lock:
                progress_store['producao'] = {'progress': 100, 'message': f'Erro: {str(e)}', 'error': True}
            
            return jsonify({'status': 'error', 'message': str(e)}), 500
            
    except Exception as e:
        print(f"Erro geral: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/progress/producao')
@bloqueio_required
def progress_producao():
    def generate():
        last_progress = None
        while True:
            with progress_lock:
                progress_data = progress_store.get('producao', {})
            
            # Só enviar se houve mudança
            if progress_data != last_progress:
                yield f"data: {json.dumps(progress_data)}\n\n"
                last_progress = progress_data.copy()
            
            # Se concluído, parar
            if progress_data.get('progress') == 100:
                break
                
            time.sleep(0.5)  # Verificar a cada 0.5 segundos
    
    return Response(generate(), mimetype='text/event-stream')

# =================================================================================================
# Configuração de Procedimentos
    
@app.route('/config', methods=['GET', 'POST'])
@bloqueio_required
def config():
    conn = get_db()

    if request.method == 'POST':
        proced = request.form.get('proced')
        print("Proced recebido:", proced)

        try:
            # === Buscar CIDs (Otimizada) ===
            cur2 = conn.cursor()
            sql2 = """
                SELECT DISTINCT spc.pacid_cid AS cid
                FROM s_pacid spc
                JOIN s_proced sp ON sp.pa_id = spc.pacid_pa
                WHERE (spc.pacid_pa || '' || sp.pa_dv) = ?
                AND spc.pacid_cid IS NOT NULL
                AND spc.pacid_cid != ''
                ORDER BY spc.pacid_cmp DESC
                LIMIT 20
            """
            cur2.execute(sql2, (proced,))
            cids = [row[0] for row in cur2.fetchall()]

            # === Buscar Serviços (Otimizada) ===
            cur3 = conn.cursor()
            sql3 = """
                SELECT DISTINCT
                    spc.pasrv_srv AS servico,
                    spc.pasrv_csf AS classificacao
                FROM s_pasrv spc
                JOIN s_proced sp ON sp.pa_id = spc.pasrv_pa
                WHERE (spc.pasrv_pa || '' || sp.pa_dv) = ?
                AND spc.pasrv_srv IS NOT NULL
                ORDER BY spc.pasrv_cmp DESC
                LIMIT 20
            """
            cur3.execute(sql3, (proced,))
            
            servico = []
            for row in cur3.fetchall():
                servico.append({
                    "servico": row[0], 
                    "classificacao": row[1]
                })

            return jsonify({
                "cids": cids, 
                "servico": servico
            })

        except Exception as e:
            print(f"Erro ao processar procedimento {proced}: {e}")
            return jsonify({"cids": [], "servico": []})

    # === GET: carrega a tela com a lista de proceds ===
    try:
        cur = conn.cursor()
        sql = "SELECT DISTINCT prd_pa FROM tb_fat_prod WHERE prd_pa IS NOT NULL ORDER BY prd_pa LIMIT 1000"
        cur.execute(sql)
        proceds = cur.fetchall()

        return render_template('config.html', proceds=proceds)
    
    except Exception as e:
        print(f"Erro ao carregar procedimentos: {e}")
        return render_template('config.html', proceds=[])

@app.route('/salvar-configuracoes', methods=['POST'])
@bloqueio_required
def salvar_configuracoes():
    try:
        data = request.get_json()
        procedimentos = data.get('procedimentos', [])
        
        conn = get_db()
        
        # Criar tabela se não existir
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tb_config_proced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proced TEXT NOT NULL,
                cid TEXT,
                servico TEXT,
                classificacao TEXT,
                UNIQUE(proced)
            )
        ''')
        conn.commit()
        
        # Contadores para feedback
        inseridos = 0
        atualizados = 0
        
        # Inserir ou atualizar dados
        for proc in procedimentos:
            # Verificar se o procedimento já existe
            existing = conn.execute(
                'SELECT id FROM tb_config_proced WHERE proced = ?', 
                (proc['proced'],)
            ).fetchone()
            
            if existing:
                # Atualizar existente
                conn.execute(
                    '''UPDATE tb_config_proced 
                       SET cid = ?, servico = ?, classificacao = ? 
                       WHERE proced = ?''',
                    (proc['cid'], proc['servico'], proc['classificacao'], proc['proced'])
                )
                atualizados += 1
            else:
                # Inserir novo
                conn.execute(
                    '''INSERT INTO tb_config_proced (proced, cid, servico, classificacao) 
                       VALUES (?, ?, ?, ?)''',
                    (proc['proced'], proc['cid'], proc['servico'], proc['classificacao'])
                )
                inseridos += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Dados salvos com sucesso! {inseridos} inseridos, {atualizados} atualizados.',
            'count': len(procedimentos)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    

@app.route('/editar-configuracao/<int:id>', methods=['POST'])
@bloqueio_required
def editar_configuracao(id):
    try:
        data = request.get_json()
        
        conn = get_db()
        conn.execute(
            'UPDATE tb_config_proced SET cid = ?, servico = ?, classificacao = ? WHERE id = ?',
            (data['cid'], data['servico'], data['classificacao'], id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Configuração atualizada!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/excluir-configuracao/<int:id>', methods=['DELETE'])
def excluir_configuracao(id):
    try:
        conn = get_db()
        conn.execute('DELETE FROM tb_config_proced WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Configuração excluída!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    
#=============================================================================================================================

def fetch_data():
    conn = get_db()
    cur = conn.cursor()
    
    query = """
        SELECT 
            prd_ident,
            prd_cnes,
            prd_cmp,
            prd_cnsmed,
            prd_cbo,
            prd_dtaten,
            prd_flh,
            prd_seq,
            prd_pa,
            prd_cnspac,
            prd_sexo,
            (SELECT co_ibge FROM tb_dados_municipio LIMIT 1) as prd_ibge,
            tcp.cid as prd_cid,
            prd_idade,
            prd_qt,
            prd_caten,
            prd_naut,
            prd_org,
            UPPER(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(
                    prd_nmpac,
                    'á', 'a'), 'à', 'a'), 'ã', 'a'), 'â', 'a'), 'ä', 'a'),
                    'é', 'e'), 'è', 'e'), 'ê', 'e'), 'ë', 'e'),
                    'í', 'i'), 'ì', 'i'), 'î', 'i'), 'ï', 'i'),
                    'ó', 'o'), 'ò', 'o'), 'õ', 'o'), 'ô', 'o'), 'ö', 'o'),
                    'ú', 'u'), 'ù', 'u'), 'û', 'u'), 'ü', 'u'),
                    'ç', 'c'), 'ñ', 'n'
                )
            ) as prd_nmpac,
            prd_dtnasc,
            raca_cor,
            etnia,
            '010' as nacionalidade,
            tcp.servico as prd_srv,
            tcp.classificacao as prd_clf,
            prd_equipe_seq,
            prd_equipe_area,
            prd_cnpj,
            prd_cep_pcnte,
            '081' as prd_lograd_pcnte,
            UPPER(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(
                    prd_end_pcnte,
                    'á', 'a'), 'à', 'a'), 'ã', 'a'), 'â', 'a'), 'ä', 'a'),
                    'é', 'e'), 'è', 'e'), 'ê', 'e'), 'ë', 'e'),
                    'í', 'i'), 'ì', 'i'), 'î', 'i'), 'ï', 'i'),
                    'ó', 'o'), 'ò', 'o'), 'õ', 'o'), 'ô', 'o'), 'ö', 'o'),
                    'ú', 'u'), 'ù', 'u'), 'û', 'u'), 'ü', 'u'),
                    'ç', 'c'), 'ñ', 'n'
                )
            ) as prd_end_pcnte,
            UPPER(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(
                    prd_compl_pcnte,
                    'á', 'a'), 'à', 'a'), 'ã', 'a'), 'â', 'a'), 'ä', 'a'),
                    'é', 'e'), 'è', 'e'), 'ê', 'e'), 'ë', 'e'),
                    'í', 'i'), 'ì', 'i'), 'î', 'i'), 'ï', 'i'),
                    'ó', 'o'), 'ò', 'o'), 'õ', 'o'), 'ô', 'o'), 'ö', 'o'),
                    'ú', 'u'), 'ù', 'u'), 'û', 'u'), 'ü', 'u'),
                    'ç', 'c'), 'ñ', 'n'
                )
            ) as prd_compl_pcnte,
            prd_num_pcnte,
            UPPER(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(
                    prd_bairro_pcnte,
                    'á', 'a'), 'à', 'a'), 'ã', 'a'), 'â', 'a'), 'ä', 'a'),
                    'é', 'e'), 'è', 'e'), 'ê', 'e'), 'ë', 'e'),
                    'í', 'i'), 'ì', 'i'), 'î', 'i'), 'ï', 'i'),
                    'ó', 'o'), 'ò', 'o'), 'õ', 'o'), 'ô', 'o'), 'ö', 'o'),
                    'ú', 'u'), 'ù', 'u'), 'û', 'u'), 'ü', 'u'),
                    'ç', 'c'), 'ñ', 'n'
                )
            ) as prd_bairro_pcnte,
            prd_ddtel_pcnte,
            prd_email_pcnte,
            ine,
            prd_fim,
            prd_cpfpac
        FROM 
            tb_fat_prod tfp
        LEFT JOIN tb_config_proced tcp 
            ON tcp.proced = tfp.prd_pa
        WHERE tfp.prd_nmpac IS NOT NULL AND tfp.prd_nmpac <> ''
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return rows

#=======================================================================================================================================

def fetch_header_data():
    conn = get_db()
    cur = conn.cursor()
    
    header_query = """
    select distinct
        sub.prd_cmp,
        SUBSTR('000000' || CAST(SUM(1) AS TEXT), -6, 6) as linhas,
        SUBSTR('000000' || sub.prd_flh, -6, 6) as folha,
        ((sum(cast(sub.prd_pa as integer)) + sum(cast(sub.prd_qt as integer))) % 1111) + 1111 as cod_controle
    from(SELECT 
            prd_ident,
            prd_cnes,
            prd_cmp,
            prd_cnsmed,
            prd_cbo,
            prd_dtaten,
            prd_flh,
            prd_seq,
            prd_pa,
            prd_cnspac,
            prd_sexo,
            prd_ibge,
            tcp.cid as prd_cid,
            prd_idade,
            prd_qt,
            prd_caten,
            prd_naut,
            prd_org,
            prd_nmpac,
            prd_dtnasc,
            raca_cor,
            etnia,
            nacionalidade,
            tcp.servico as prd_srv,
            tcp.classificacao as prd_clf,
            prd_equipe_seq,
            prd_equipe_area,
            prd_cnpj,
            prd_cep_pcnte,
            prd_lograd_pcnte,
            prd_end_pcnte,
            prd_compl_pcnte,
            prd_num_pcnte,
            prd_bairro_pcnte,
            prd_ddtel_pcnte,
            prd_email_pcnte,
            ine,
            prd_fim,
            prd_cpfpac
        FROM 
            tb_fat_prod tfp
        LEFT JOIN tb_config_proced tcp 
            ON tcp.proced = tfp.prd_pa) sub 
    """
    
    cur.execute(header_query)
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return result if result else ("default1", "default2", "default3", "default4")

def remove_acentos(texto):
    """
    Remove acentos e caracteres especiais de um texto
    """
    if texto is None:
        return texto
        
    # Dicionário de substituições
    substituicoes = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', 'ñ': 'n',
        'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
        'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
        'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'Ç': 'C', 'Ñ': 'N'
    }
    
    # Aplicar substituições
    for acento, sem_acento in substituicoes.items():
        texto = texto.replace(acento, sem_acento)
    
    return texto

def format_row(row):
    # Remover acentos dos campos de texto antes de formatar
    campos_sem_acentos = []
    for i, valor in enumerate(row):
        if i in [18, 30, 31, 32, 33, 34]:  # Índices dos campos que precisam ter acentos removidos
            # prd_nmpac (18), prd_end_pcnte (30), prd_compl_pcnte (32), prd_bairro_pcnte (34)
            campos_sem_acentos.append(remove_acentos(str(valor or '')))
        else:
            campos_sem_acentos.append(str(valor or ''))
    
    fields = [
        (campos_sem_acentos[0], 2),    # prd_ident
        (campos_sem_acentos[1], 7),    # prd_cnes
        (campos_sem_acentos[2], 6),    # prd_cmp
        (campos_sem_acentos[3], 15),   # prd_cnsmed
        (campos_sem_acentos[4], 6),    # prd_cbo
        (campos_sem_acentos[5], 8),    # prd_dtaten
        (campos_sem_acentos[6], 3),    # prd_flh
        (campos_sem_acentos[7], 2),    # prd_seq
        (campos_sem_acentos[8], 10),   # prd_pa
        (campos_sem_acentos[9], 15),   # prd_cnspac
        (campos_sem_acentos[10], 1),   # prd_sexo
        (campos_sem_acentos[11], 6),   # prd_ibge
        (campos_sem_acentos[12], 4),   # prd_cid
        (campos_sem_acentos[13], 3),   # prd_idade
        (campos_sem_acentos[14], 6),   # prd_qt
        (campos_sem_acentos[15], 2),   # prd_caten
        (campos_sem_acentos[16], 13),  # prd_naut
        (campos_sem_acentos[17], 3),   # prd_org
        (campos_sem_acentos[18], 30),  # prd_nmpac (sem acentos)
        (campos_sem_acentos[19], 8),   # prd_dtnasc
        (campos_sem_acentos[20], 2),   # raca_cor
        (campos_sem_acentos[21], 4),   # etnia
        (campos_sem_acentos[22], 3),   # nacionalidade
        (campos_sem_acentos[23], 3),   # prd_srv
        (campos_sem_acentos[24], 3),   # prd_clf
        (campos_sem_acentos[25], 8),   # prd_equipe_seq
        (campos_sem_acentos[26], 4),   # prd_equipe_area
        (campos_sem_acentos[27], 14),  # prd_cnpj
        (campos_sem_acentos[28], 8),   # prd_cep_pcnte
        (campos_sem_acentos[29], 3),   # prd_lograd_pcnte
        (campos_sem_acentos[30], 30),  # prd_end_pcnte (sem acentos)
        (campos_sem_acentos[31], 10),  # prd_num_pcnte
        (campos_sem_acentos[32], 5),   # prd_compl_pcnte (sem acentos)
        (campos_sem_acentos[33], 30),  # prd_bairro_pcnte (sem acentos)
        (campos_sem_acentos[34], 11),  # prd_ddtel_pcnte
        (campos_sem_acentos[35], 40),  # prd_email_pcnte
        (campos_sem_acentos[36], 10),  # ine
        (campos_sem_acentos[38], 11),   # prd_cpfpac
        (campos_sem_acentos[37], 2)   # prd_fim
    ]
    
    formatted_row = "".join([str(field).ljust(length)[:length] for field, length in fields])
    return formatted_row

downloads_folder = str(Path.home() / "Downloads")

@app.route('/export', methods=['GET', 'POST'])
@bloqueio_required
def export_data():
    # Fetch data to be exported
    data = fetch_data()

    # Depuração: mostrar todos os valores de row[2] para inspecionar o formato
    for row in data:
        print(f"Valor de row[2]: {row[2]} (tipo: {type(row[2])})")

    # Usar todos os dados sem filtro
    filtered_data = data

    # Depuração: Mostrar o resultado
    print(f"Dados exportados: {len(filtered_data)} registros")
    
    # Fetch dynamic header values from SQL
    conn = get_db()  # Assume this function provides a database connection
    cursor = conn.cursor()
    
    # Execute the query
    cursor.execute("""
        SELECT 
            no_municipio, 
            ds_sigla, 
            nu_cnes, 
            nu_cnpj
        FROM tb_dados_municipio
    """)
    
    # Fetch the results
    row = cursor.fetchone()
    cursor.close()

    cur2 = conn.cursor()
    
    # Execute the query
    cur2.execute("""
        SELECT DISTINCT prd_cmp
        FROM tb_fat_prod
        LIMIT 1
    """)
    data_comp = cur2.fetchone()
    if row:
        print(data_comp[0])

    cur2.close()

    conn.close()
    
    if row:
        no_municipio, ds_sigla, nu_cnes, nu_cnpj = row
    else:
        no_municipio, ds_sigla, nu_cnes, nu_cnpj = "", "", "", ""

    value1, value2, value3, value4 = fetch_header_data()
    
    # Create the header with dynamic values
    # Nota: A competência foi removida do header, você pode ajustar conforme necessário
    header = f"01#BPA#{data_comp[0]}{value2}{value3}{value4}SMS {no_municipio:<20} {nu_cnes}{nu_cnpj}SRS - {ds_sigla}                                ED04.01"
    
    # Format the data with '\r\n'
    formatted_data = "\r\n".join([format_row(row) for row in filtered_data])
    #print("Formatted Data:\n", formatted_data)
    
    # Combine the header and formatted data with '\r\n'
    full_content = header + "\r\n" + formatted_data + "\r\n"
    #print("Full Content:", full_content)
    
    # --- Salvar na pasta Downloads ---
    downloads_folder = Path.home() / "Downloads"
    file_path = downloads_folder / "data.txt"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    # --- Abrir o Explorer (opcional) ---
    if platform.system() == "Windows":
        os.startfile(downloads_folder)

    # --- Retorna apenas a mensagem ---
    return jsonify({
        "success": True,
        "msg": f"Arquivo salvo em: {file_path}"
    })
    

@app.route('/exportar_txt', methods=['POST'])
@bloqueio_required
def exportar_txt():
    try:
        # Conexão com o banco de dados
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            prd_ident,
            prd_cnes,
            prd_cmp,
            prd_cnsmed,
            prd_cbo,
            prd_dtaten,
            prd_flh,
            prd_seq,
            prd_pa,
            prd_cnspac,
            prd_sexo,
            prd_ibge,
            tcp.cid as prd_cid,
            prd_idade,
            prd_qt,
            prd_caten,
            prd_naut,
            prd_org,
            prd_nmpac,
            prd_dtnasc,
            raca_cor,
            etnia,
            nacionalidade,
            tcp.servico as prd_srv,
            tcp.classificacao as prd_clf,
            prd_equipe_seq,
            prd_equipe_area,
            prd_cnpj,
            prd_cep_pcnte,
            prd_lograd_pcnte,
            prd_end_pcnte,
            prd_compl_pcnte,
            prd_num_pcnte,
            prd_bairro_pcnte,
            prd_ddtel_pcnte,
            prd_email_pcnte,
            ine,
            prd_fim,
            prd_cpfpac
        FROM 
            tb_fat_prod tfp
        LEFT JOIN tb_config_proced tcp 
            ON tcp.proced = tfp.prd_pa
        """
        
        cursor.execute(query)
        resultados = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        output = io.StringIO()
        
        # Cabeçalho fixo (sem #)
        cabecalho = "01#BPA#2025070000020000011280UNIDADE SAUDE                  99999999999999999999SECRETARIA DE SAUDE DE ESMERALDAS          MD04.10"
        output.write(cabecalho + '\n')
        
        for item in resultados:
            # Definir cada campo com tamanho fixo usando ljust()
            linha_dados = [
                str(item[0] or '').ljust(2),    # prd_ident (2)
                str(item[1] or '').ljust(7),    # prd_cnes (7)
                str(item[2] or '').ljust(6),    # prd_cmp (6)
                str(item[3] or '').ljust(15),   # prd_cnsmed (15)
                str(item[4] or '').ljust(6),    # prd_cbo (6)
                str(item[5] or '').ljust(8),    # prd_dtaten (8)
                str(item[6] or '').ljust(3),    # prd_flh (3)
                str(item[7] or '').ljust(2),    # prd_seq (2)
                str(item[8] or '').ljust(10),   # prd_pa (10)
                str(item[9] or '').ljust(15),   # prd_cnspac (15)
                str(item[10] or '').ljust(1),   # prd_sexo (1)
                str(item[11] or '').ljust(6),   # prd_ibge (6)
                str(item[12] or '').ljust(4),   # prd_cid (4)
                str(item[13] or '').ljust(3),   # prd_idade (3)
                str(item[14] or '').ljust(6),   # prd_qt (6)
                str(item[15] or '').ljust(2),   # prd_caten (2)
                str(item[16] or '').ljust(13),  # prd_naut (13)
                str(item[17] or '').ljust(3),   # prd_org (3)
                str(item[18] or '').ljust(30),  # prd_nmpac (30)
                str(item[19] or '').ljust(8),   # prd_dtnasc (8)
                str(item[20] or '').ljust(2),   # raca_cor (2)
                str(item[21] or '').ljust(4),   # etnia (4)
                str(item[22] or '').ljust(3),   # nacionalidade (3)
                str(item[23] or '').ljust(3),   # prd_srv (3)
                str(item[24] or '').ljust(3),   # prd_clf (3)
                str(item[25] or '').ljust(8),   # prd_equipe_seq (8)
                str(item[26] or '').ljust(4),   # prd_equipe_area (4)
                str(item[27] or '').ljust(14),  # prd_cnpj (14)
                str(item[28] or '').ljust(8),   # prd_cep_pcnte (8)
                str(item[29] or '').ljust(3),   # prd_lograd_pcnte (3)
                str(item[30] or '').ljust(30),  # prd_end_pcnte (30)
                str(item[31] or '').ljust(10),  # prd_compl_pcnte (10)
                str(item[32] or '').ljust(5),   # prd_num_pcnte (5)
                str(item[33] or '').ljust(30),  # prd_bairro_pcnte (30)
                str(item[34] or '').ljust(11),  # prd_ddtel_pcnte (11)
                str(item[35] or '').ljust(40),  # prd_email_pcnte (40)
                str(item[36] or '').ljust(10),  # ine (10)
                str(item[37] or '').ljust(2),   # prd_fim (2)
                str(item[38] or '').ljust(11)   # prd_cpfpac (11)
            ]
            
            # Juntar todos os campos sem separadores
            linha_formatada = ''.join(linha_dados)
            output.write(linha_formatada + '\n')
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment;filename=dados_bpa.txt"}
        )
    
    except Exception as e:
        return f"Erro ao exportar: {str(e)}", 500
    
#=================================================================================================================
# Dados do Município

@app.route('/municipio_page')
def municipio_page():
    """Página dedicada para gerenciamento de municípios"""
    return render_template('municipio.html')

# API para listar municípios
@app.route('/api/municipios', methods=['GET'])
@bloqueio_required
def get_municipios():
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT rowid, no_municipio, ds_sigla, nu_cnes, nu_cnpj, co_ibge FROM tb_dados_municipio ORDER BY no_municipio")
        municipios = []
        for row in cursor.fetchall():
            municipios.append({
                'rowid': row[0],
                'no_municipio': row[1],
                'ds_sigla': row[2],
                'nu_cnes': row[3],
                'nu_cnpj': row[4],
                'co_ibge': row[5]
            })
        return jsonify(municipios)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# API para obter um município específico
@app.route('/api/municipio/<int:id>', methods=['GET'])
@bloqueio_required
def get_municipio(id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT rowid, * FROM tb_dados_municipio WHERE rowid = ?", (id,))
        row = cursor.fetchone()
        if row:
            return jsonify({
                'rowid': row[0],
                'no_municipio': row[1],
                'ds_sigla': row[2],
                'nu_cnes': row[3],
                'nu_cnpj': row[4],
                'co_ibge': row[5]
            })
        else:
            return jsonify({"error": "Município não encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# API para criar/editar município
@app.route('/api/municipio', methods=['POST'])
@bloqueio_required
def api_create_municipio():
    data = request.get_json()
    
    no_municipio = data.get('no_municipio') 
    ds_sigla = data.get('ds_sigla') 
    nu_cnes = data.get('nu_cnes')
    nu_cnpj = data.get('nu_cnpj') 
    co_ibge = data.get('co_ibge')
    rowid = data.get('id_registro')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        if rowid:  # Edição
            cursor.execute("""
                UPDATE tb_dados_municipio 
                SET no_municipio = upper(?), ds_sigla = ?, nu_cnes = ?, nu_cnpj = ?, co_ibge = ?
                WHERE rowid = ?
            """, (no_municipio, ds_sigla, nu_cnes, nu_cnpj, co_ibge, rowid))
        else:  # Criação
            cursor.execute("""
                INSERT INTO tb_dados_municipio 
                    (no_municipio, ds_sigla, nu_cnes, nu_cnpj, co_ibge) 
                VALUES (upper(?), ?, ?, ?, ?)
            """, (no_municipio, ds_sigla, nu_cnes, nu_cnpj, co_ibge))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# API para excluir município (mantida a mesma)
@app.route('/api/municipio/<int:id>', methods=['DELETE'])
@bloqueio_required
def api_delete_municipio(id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM tb_dados_municipio WHERE rowid = ?", (id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

def start_flask():
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Roda o Flask em paralelo
    t = threading.Thread(target=start_flask)
    t.daemon = True
    t.start()

    # Abre a WebView apontando para o Flask
    webview.create_window("CONVERSOR PEC BPA", "http://127.0.0.1:5000/")
    webview.start()
