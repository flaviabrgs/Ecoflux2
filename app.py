import os
import math
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import bcrypt

app = Flask(__name__)
app.secret_key = "ecoflux_ufrpe_secret_key_prod_safe"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Tabela de Pontuação por Decomposição
PONTUACAO_RESIDUOS = {
    "VIDRO": 100,
    "PLASTICO": 60,
    "METAL": 40,
    "PAPEL": 10,
    "ORGANICO": 5
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha_hash BLOB NOT NULL,
        data_nasc TEXT NOT NULL,
        curso TEXT NOT NULL,
        role TEXT DEFAULT 'ALUNO',
        saldo_pontos INTEGER DEFAULT 0,
        falhas_login INTEGER DEFAULT 0,
        bloqueado_ate TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pontos_descarte (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        bloco TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        ativo INTEGER DEFAULT 1,
        qr_token TEXT UNIQUE NOT NULL,
        capacidade_litros INTEGER DEFAULT 200
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS descartes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        ponto_id INTEGER,
        tipo_residuo TEXT NOT NULL,
        foto_url TEXT,
        pontos_ganhos INTEGER NOT NULL,
        data_hora TEXT NOT NULL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY(ponto_id) REFERENCES pontos_descarte(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reportes_zeladoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        ponto_id INTEGER,
        tipo_problema TEXT NOT NULL,
        data_reporte TEXT NOT NULL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY(ponto_id) REFERENCES pontos_descarte(id)
    )
    """)

    # Seed inicial de PEVs no Campus UFRPE Dois Irmãos se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) as count FROM pontos_descarte")
    if cursor.fetchone()["count"] == 0:
        pevs = [
            ("PEV CEAGRI - Central", "Bloco Central / CEAGRI", -8.01635, -34.95015, "ECO-CEAGRI-01", 240),
            ("PEV BSI - Informática", "Prédio da Computação", -8.01750, -34.94920, "ECO-BSI-02", 200),
            ("PEV RU - Restaurante Universitário", "Refeitório Central", -8.01520, -34.94880, "ECO-RU-03", 400),
            ("PEV Zootecnia", "Departamento de Zootecnia", -8.01890, -34.95210, "ECO-ZOO-04", 180)
        ]
        cursor.executemany("""
            INSERT INTO pontos_descarte (nome, bloco, latitude, longitude, qr_token, capacidade_litros)
            VALUES (?, ?, ?, ?, ?, ?)
        """, pevs)

    conn.commit()
    conn.close()

init_db()

# --- Geofencing: Fórmula de Haversine ---
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Raio da Terra em metros
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- Middleware de Sessão ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Por favor, autentique-se para continuar.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- Rotas de Autenticação ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        
        conn = get_db()
        user = conn.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
        agora = datetime.utcnow()

        if user:
            # Checa rate limit de 30 segundos
            if user["bloqueado_ate"]:
                bloqueio = datetime.fromisoformat(user["bloqueado_ate"])
                if agora < bloqueio:
                    segundos_restantes = int((bloqueio - agora).total_seconds())
                    conn.close()
                    flash(f"Acesso bloqueado por tentativas falhas. Aguarde {segundos_restantes}s.", "danger")
                    return render_template("login.html")

            # Verifica credenciais
            if bcrypt.checkpw(senha.encode("utf-8"), user["senha_hash"]):
                conn.execute("UPDATE usuarios SET falhas_login = 0, bloqueado_ate = NULL WHERE id = ?", (user["id"],))
                conn.commit()
                session["user_id"] = user["id"]
                session["user_nome"] = user["nome"]
                session["user_role"] = user["role"]
                conn.close()
                return redirect(url_for("index"))
            else:
                novas_falhas = user["falhas_login"] + 1
                bloqueado_ate = None
                if novas_falhas >= 3:
                    bloqueado_ate = (agora + timedelta(seconds=30)).isoformat()
                    novas_falhas = 0
                    flash("3 falhas detectadas. Conta temporariamente suspensa por 30s.", "danger")
                else:
                    flash(f"Credenciais inválidas. Falha {novas_falhas} de 3.", "warning")

                conn.execute("UPDATE usuarios SET falhas_login = ?, bloqueado_ate = ? WHERE id = ?",
                             (novas_falhas, bloqueado_ate, user["id"]))
                conn.commit()
                conn.close()
                return render_template("login.html")

        conn.close()
        flash("Usuário não cadastrado.", "danger")
    return render_template("login.html")

@app.route("/cadastro", methods=["POST"])
def cadastro():
    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")
    data_nasc = request.form.get("data_nasc", "").strip()
    curso = request.form.get("curso", "").strip()

    if not all([nome, email, senha, data_nasc, curso]):
        flash("Preencha todos os campos obrigatórios.", "danger")
        return redirect(url_for("login"))

    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO usuarios (nome, email, senha_hash, data_nasc, curso)
            VALUES (?, ?, ?, ?, ?)
        """, (nome, email, senha_hash, data_nasc, curso))
        conn.commit()
        flash("Conta registrada com sucesso! Realize o login.", "success")
    except sqlite3.IntegrityError:
        flash("Este e-mail já está registrado na plataforma.", "warning")
    finally:
        conn.close()

    return redirect(url_for("login"))

@app.route("/recuperar-senha", methods=["POST"])
def recuperar_senha():
    email = request.form.get("email", "").strip().lower()
    data_nasc = request.form.get("data_nasc", "").strip()
    nova_senha = request.form.get("nova_senha", "")

    conn = get_db()
    user = conn.execute("SELECT * FROM usuarios WHERE email = ? AND data_nasc = ?", (email, data_nasc)).fetchone()

    if user:
        novo_hash = bcrypt.hashpw(nova_senha.encode("utf-8"), bcrypt.gensalt())
        conn.execute("UPDATE usuarios SET senha_hash = ?, falhas_login = 0, bloqueado_ate = NULL WHERE id = ?", 
                     (novo_hash, user["id"]))
        conn.commit()
        flash("Senha redefinida com sucesso. Acesse com sua nova chave.", "success")
    else:
        flash("Os dados fornecidos não coincidem com o cadastro.", "danger")

    conn.close()
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- Rotas da Aplicação ---
@app.route("/")
@login_required
def index():
    conn = get_db()
    user = conn.execute("SELECT saldo_pontos FROM usuarios WHERE id = ?", (session["user_id"],)).fetchone()
    pontos = conn.execute("SELECT * FROM pontos_descarte WHERE ativo = 1").fetchall()
    conn.close()
    return render_template("index.html", user_pontos=user["saldo_pontos"], pevs=[dict(p) for p in pontos])

@app.route("/descarte")
@login_required
def descarte():
    return render_template("descarte.html")

@app.route("/api/processar-descarte", methods=["POST"])
@login_required
def processar_descarte():
    qr_token = request.form.get("qr_token", "").strip()
    tipo_residuo = request.form.get("tipo_residuo", "").strip().upper()
    lat_usuario = request.form.get("latitude", type=float)
    lon_usuario = request.form.get("longitude", type=float)
    foto = request.files.get("foto")

    if not all([qr_token, tipo_residuo, lat_usuario, lon_usuario, foto]):
        return jsonify({"success": False, "message": "Dados incompletos enviados ao servidor."}), 400

    if tipo_residuo not in PONTUACAO_RESIDUOS:
        return jsonify({"success": False, "message": "Tipo de resíduo não catalogado."}), 400

    conn = get_db()
    pev = conn.execute("SELECT * FROM pontos_descarte WHERE qr_token = ? AND ativo = 1", (qr_token,)).fetchone()
    
    if not pev:
        conn.close()
        return jsonify({"success": False, "message": "Ponto de Entrega Voluntária não reconhecido."}), 404

    # Validação de Geofencing (30 metros)
    distancia = haversine_distance(lat_usuario, lon_usuario, pev["latitude"], pev["longitude"])
    if distancia > 30.0:
        conn.close()
        return jsonify({
            "success": False, 
            "message": f"Você está a {int(distancia)}m do PEV. Aproxime-se a menos de 30m para confirmar o descarte."
        }), 403

    # Salva foto
    filename = f"{session['user_id']}_{int(datetime.utcnow().timestamp())}_{foto.filename}"
    caminho_foto = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    foto.save(caminho_foto)

    pontos = PONTUACAO_RESIDUOS[tipo_residuo]
    agora_str = datetime.utcnow().isoformat()

    conn.execute("""
        INSERT INTO descartes (usuario_id, ponto_id, tipo_residuo, foto_url, pontos_ganhos, data_hora)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session["user_id"], pev["id"], tipo_residuo, filename, pontos, agora_str))

    conn.execute("UPDATE usuarios SET saldo_pontos = saldo_pontos + ? WHERE id = ?", (pontos, session["user_id"]))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "pontos": pontos, "message": "Descarte homologado com sucesso!"})

@app.route("/ranking")
@login_required
def ranking():
    conn = get_db()
    ranking_individual = conn.execute("""
        SELECT nome, curso, saldo_pontos 
        FROM usuarios 
        ORDER BY saldo_pontos DESC 
        LIMIT 10
    """).fetchall()

    ranking_cursos = conn.execute("""
        SELECT curso, SUM(saldo_pontos) as total_pontos, COUNT(id) as total_alunos
        FROM usuarios 
        GROUP BY curso 
        ORDER BY total_pontos DESC
    """).fetchall()
    
    conn.close()
    return render_template("ranking.html", individual=ranking_individual, cursos=ranking_cursos)

@app.route("/perfil")
@login_required
def perfil():
    conn = get_db()
    user = conn.execute("SELECT * FROM usuarios WHERE id = ?", (session["user_id"],)).fetchone()
    historico = conn.execute("""
        SELECT d.*, p.nome as nome_pev 
        FROM descartes d
        JOIN pontos_descarte p ON d.ponto_id = p.id
        WHERE d.usuario_id = ?
        ORDER BY d.id DESC LIMIT 5
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("base.html", perfil_view=True, user=user, historico=historico)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
if __name__ == '__main__':
    # ssl_context='adhoc' gera um certificado SSL temporário
    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context='adhoc')