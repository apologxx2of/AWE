# app.py
# Verifique "LICENSE" para mais informações sobre redistribuição e uso do Software.
# Copyright (c) 2025 Lusomedia™
# Este software está sob a licença Lusomedia™ License 1.0. Veja "LICENSE" para mais informações.
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import os
import json
import requests
import random
import re
import uuid
import bleach
from markupsafe import escape
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["60 per minute"]
)

CONFIG_PATH = "config.json"

# Carrega config do arquivo ou cria default
def load_config():
    if not os.path.exists(CONFIG_PATH):
        config = {
            "APP_TITLE": "EXAMPLE",
            "LICENSE": "EXAMPLE",
            "DB_FILE": "EXAMPLE.db"
        }
        return config

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except:            
            APP_TITLE = EXAMPLE
            LICENSE = EXAMPLE
            DB_FILE = EXAMPLE.db
        return config

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# --- Inicializa config ---
config = load_config()
APP_TITLE = config.get("APP_TITLE")
LICENSE = config.get("LICENSE")
DB_FILE = config.get("DB_FILE")

UPLOAD_FOLDER = "static/uploads"

app = Flask(__name__)
app.secret_key = "tá_ligado123"  # troca isso pelo amor de Deus
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

csrf = CSRFProtect(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB

app.config.update(
    SESSION_COOKIE_SECURE=True,   # só HTTPS
    SESSION_COOKIE_HTTPONLY=True, # JS não consegue ler
    SESSION_COOKIE_SAMESITE='Lax' # previne CSRF básico
)

# ---------- JINJA FILTER ----------
@app.template_filter('fmt_dt')
def fmt_dt(value):
    if not value:
        return "Desconhecida"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return value

# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(
        DB_FILE,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        timeout=5,              # espera 5s se o banco estiver ocupado
        check_same_thread=False  # permite usar a conexão em threads diferentes
    )
    conn.row_factory = sqlite3.Row
    # ativa foreign keys pra manter integridade
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_user():
    if 'username' not in session:
        return None
    username = session['username']
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return {'id': row['id'], 'username': row['username'], 'is_admin': row['is_admin']}
    return None

def init_db():
    first = not os.path.exists(DB_FILE)
    conn = get_db()
    c = conn.cursor()

    # USERS
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    )
    ''')

    # ARTICLES
    c.execute('''
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        last_edited TEXT,
        last_editor TEXT
    )
    ''')

    # ARTICLE HISTORY
    c.execute('''
    CREATE TABLE IF NOT EXISTS article_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        content TEXT NOT NULL,
        ts TEXT NOT NULL,
        user TEXT,
        summary TEXT
    )
    ''')

    # DISCUSSIONS (topics + replies)
    c.execute('''
    CREATE TABLE IF NOT EXISTS discussions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        parent_id INTEGER,
        topic_title TEXT,
        comment_text TEXT NOT NULL,
        user TEXT,
        reply_to TEXT,
        ts TEXT
    )
    ''')

    conn.commit()

    # Popula DB inicial
    if first:
        try:
            # usuário admin
            c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                      ("admin", "batman17K", 1))

            # artigo inicial
            c.execute("""
                INSERT INTO articles (slug, title, content, last_edited, last_editor)
                VALUES (?, ?, ?, ?, ?)
            """, (
                f"{APP_TITLE}:PP",
                f"{APP_TITLE}:PP",
                f"""Olá, parece que você acabou de instalar a AWE!\nA Wiki {APP_TITLE} já foi configurada e agora você pode expandir-ela!\nTambém confira nossas recomendações no site!\nObrigado por instalar a ApoloWikiEngine (AWE).\n==Mais==\nVeja no site:\n1. Como personalizar melhor minha wiki?\n2. Como funciona a AWE?\n3. Como posso adaptar do php (MediaWiki) para python?""",
                datetime.now().isoformat(),
                "admin"
            ))

            conn.commit()
            print("DB criada e povoada (usuario admin/admin).")
        except Exception as e:
            print("Falha ao povoar DB inicial:", e)

    conn.close()

# ---------- HELPERS ----------
safe = escape(texto)

def sanitize_text(text):
    # lista branca mínima
    allowed_tags = []
    allowed_attrs = {}

    return bleach.clean(
        text,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )

def get_user():
    if 'username' in session:
        return {'username': session['username']}
    return None

def get_real_ip():
    try:
        r = requests.get("https://meuip.com/api/meuip.php", timeout=2)
        ip = r.text.strip()
        return ip
    except:
        return None

@limiter.limit("50 per minute")
@app.after_request
def set_csp(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none';"
    )
    return response

# ---------- ROUTES PRINCIPAIS ----------
# home
@app.route('/')
def home():
    cu = get_user()
    conn = get_db()
    c = conn.cursor()
    # tenta pegar o artigo Lusopédia:PP
    c.execute("SELECT * FROM articles WHERE slug=?", ("Lusopédia:PP",))
    article = c.fetchone()
    if not article:
        c.execute("""
                INSERT INTO articles (slug, title, content, last_edited, last_editor)
                VALUES (?, ?, ?, ?, ?)
            """, (
                f"{APP_TITLE}:PP",
                f"{APP_TITLE}:PP",
                f"""Olá, parece que você acabou de instalar a AWE!\nA Wiki {APP_TITLE} já foi configurada e agora você pode expandir-ela!\nTambém confira nossas recomendações no site!\nObrigado por instalar a ApoloWikiEngine (AWE).\n==Mais==\nVeja no site:\n1. Como personalizar melhor minha wiki?\n2. Como funciona a AWE?\n3. Como posso adaptar do php (MediaWiki) para python?""",
                datetime.now().isoformat(),
                "admin"
        ))
    # pega tópicos do artigo
    c.execute("SELECT * FROM discussions WHERE article_id=? AND parent_id IS NULL ORDER BY ts DESC", (article['id'],))
    topics = c.fetchall()
    # pega replies
    replies_map = {}
    c.execute("SELECT * FROM discussions WHERE article_id=? AND parent_id IS NOT NULL ORDER BY ts ASC", (article['id'],))
    replies = c.fetchall()
    for r in replies:
        replies_map.setdefault(r['parent_id'], []).append(r)
    conn.close()
    if os.path.exists(CONFIG_PATH):
        return render_template("article.html", APP_TITLE=APP_TITLE, cu=cu, title=article['title'],
                           slug=article['slug'], content=article['content'],
                           discussion_topics=topics, discussion_replies=replies_map,
                           last_edited=article['last_edited'], LICENSE=LICENSE)
    else:
        return redirect("config")

# configurador
@app.route("/config", methods=["GET", "POST"])
def edit_config():
    global APP_TITLE, LICENSE, DB_FILE
    if request.method == "POST":
        APP_TITLE = request.form.get("APP_TITLE","").strip() or APP_TITLE
        LICENSE = request.form.get("LICENSE","").strip() or LICENSE
        DB_FILE = request.form.get("DB_FILE","").strip() or DB_FILE

        save_config({
            "APP_TITLE": APP_TITLE,
            "LICENSE": LICENSE,
            "DB_FILE": DB_FILE
        })
        flash("Configurações salvas!", "success")
        init_db()
        return redirect(url_for("edit_config"))

    return render_template("config.html",
        APP_TITLE=APP_TITLE,
        LICENSE=LICENSE,
        DB_FILE=DB_FILE
    )

# goto geral: aceita "random", "edit_article/<slug>", "history/<slug>" ou slug de artigo
@app.route('/wiki/<path:slug>')
def goto(slug):
    cu = get_user()
    conn = get_db()
    c = conn.cursor()

    # --- Casos especiais ---
    if slug == 'random':
        c.execute("SELECT slug FROM articles")
        rows = c.fetchall()
        if not rows:
            flash("Sem artigos ainda.", "error")
            conn.close()
            return redirect(url_for('home'))
        r = random.choice(rows)['slug']
        conn.close()
        return redirect(url_for('goto', slug=r))

    if slug.startswith('edit_article/'):
        inner = slug.split('/', 1)[1]
        conn.close()
        return redirect(url_for('edit_article', slug=inner))

    if slug.startswith('history/'):
        inner = slug.split('/', 1)[1]
        conn.close()
        return redirect(url_for('history', slug=inner))

    # --- Pega artigo principal ---
    c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
    article = c.fetchone()

    if not article:
        # tenta pelo título
        c.execute("SELECT * FROM articles WHERE title LIKE ?", ('%'+slug+'%',))
        article = c.fetchone()
        if not article:
            flash(f"Artigo não encontrado: {slug}", "error")
            conn.close()
            return redirect(url_for('home'))

    article_id = article['id']

    # --- Pega discussões ---
    c.execute("SELECT * FROM discussions WHERE article_id=? AND parent_id IS NULL ORDER BY ts DESC", (article_id,))
    topics = c.fetchall()

    c.execute("SELECT * FROM discussions WHERE article_id=? AND parent_id IS NOT NULL ORDER BY ts ASC", (article_id,))
    replies = c.fetchall()
    replies_map = {}
    for r in replies:
        replies_map.setdefault(r['parent_id'], []).append(r)

    # --- Pega histórico ---
    c.execute("SELECT id, content, ts, user, summary FROM article_history WHERE slug=? ORDER BY ts DESC", (slug,))
    article_history = c.fetchall()

    conn.close()

    return render_template(
        "article.html",
        APP_TITLE=APP_TITLE,
        cu=cu,
        title=article['title'],
        slug=article['slug'],
        content=article['content'],
        discussion_topics=topics,
        discussion_replies=replies_map,
        article_history=article_history,
        last_edited=article['last_edited'],
        LICENSE=LICENSE
    )

# EDIT ARTICLE
@app.route('/edit_article/<slug>', methods=['GET', 'POST'])
def edit_article(slug):
    cu = get_user()
    if not cu:
        flash(f"É necessário fazer logon em uma conta da {APP_TITLE}.", "error")
        return redirect(url_for('home'))

    conn = get_db()
    c = conn.cursor()

    # Pega artigo ou cria se não existir
    c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
    article = c.fetchone()
    if not article:
        timestamp = datetime.now().isoformat()
        c.execute(
            "INSERT INTO articles (slug, title, content, last_edited) VALUES (?, ?, ?, ?)",
            (slug, slug, "<p>Artigo criado.</p>", timestamp)
        )
        conn.commit()
        c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
        article = c.fetchone()

    if request.method == 'POST':
        new_content = request.form.get('content','').strip()
        if new_content == article['content']:
            flash("Nenhuma alteração feita.", "info")
            conn.close()
            return redirect(url_for('goto', slug=slug))

        timestamp = datetime.now().isoformat()

        # SALVA VERSÃO NOVA NO HISTÓRICO
        c.execute("""
            INSERT INTO article_history (slug, content, ts, user)
            VALUES (?, ?, ?, ?)
        """, (slug, new_content, timestamp, cu['username']))

        # ATUALIZA ARTIGO PRINCIPAL
        c.execute("""
            UPDATE articles
            SET content=?, last_edited=?, last_editor=?
            WHERE slug=?
        """, (new_content, timestamp, cu['username'], slug))

        conn.commit()
        conn.close()
        flash("Artigo atualizado e versão salva no histórico!", "success")
        return redirect(url_for('goto', slug=slug))

    conn.close()
    return render_template("edit_article.html",
        APP_TITLE=APP_TITLE,
        cu=cu,
        title=article['title'],
        content=article['content'],
        slug=slug,
        LICENSE=LICENSE
    )

@app.route('/article/<slug>/discussion', methods=['POST'])
def add_discussion(slug):
    cu = get_user()
    user = cu['username'] if cu else get_real_ip()
    topic_title = request.form.get('topic_title','').strip()
    comment_text = request.form.get('comment_text','').strip()

    if not comment_text:
        flash("Mensagem vazia.", "error")
        return redirect(url_for('goto', slug=slug))

    conn = get_db()
    c = conn.cursor()

    # Garante que o artigo existe, cria se for user:<username>
    c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
    article = c.fetchone()
    if not article:
        # Se for perfil de usuário, cria o "artigo de usuário"
        if slug.startswith("user:"):
            username = slug.split(":",1)[1]
            timestamp = datetime.now().isoformat()
            c.execute("""
                INSERT INTO articles (slug, title, content, last_edited)
                VALUES (?, ?, ?, ?)
            """, (slug, f"Perfil de {username}", f"<p>Perfil de {username} criado.</p>", timestamp))
            conn.commit()
            c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
            article = c.fetchone()
        else:
            flash("Artigo inexistente.", "error")
            conn.close()
            return redirect(url_for('home'))

    flash("Tópico criado com sucesso!", "success")
    return redirect(url_for('goto', slug=slug))

@app.route('/article/<path:slug>/discussion/<int:topic_id>/reply', methods=['POST'])
def reply_discussion(slug, topic_id):
    cu = get_user()
    user = cu['username'] if cu else request.remote_addr
    comment_text = request.form.get('reply_text','').strip()
    reply_to = request.form.get('reply_to','').strip() or None
    if not comment_text:
        flash("Resposta vazia.", "error")
        return redirect(url_for('goto', slug=slug))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM articles WHERE slug=?", (slug,))
    art = c.fetchone()
    if not art:
        flash("Artigo inexistente.", "error")
        conn.close()
        return redirect(url_for('home'))
    # ensure topic exists
    c.execute("SELECT id, user FROM discussions WHERE id=? AND article_id=? AND parent_id IS NULL", (topic_id, art['id']))
    topic = c.fetchone()
    if not topic:
        flash("Tópico inexistente.", "error")
        conn.close()
        return redirect(url_for('goto', slug=slug))

    c.execute("INSERT INTO discussions (article_id, parent_id, topic_title, comment_text, user, reply_to, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (art['id'], topic_id, None, comment_text, user, reply_to, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    flash("Resposta adicionada!", "success")
    return redirect(url_for('goto', slug=slug))

@app.route('/user/<username>/discussion', methods=['POST'])
def add_user_discussion(username):
    cu = get_user()
    user = cu['username'] if cu else request.remote_addr
    topic_title = request.form.get('topic_title','').strip()
    comment_text = request.form.get('comment_text','').strip()

    if not comment_text:
        flash("Mensagem vazia.", "error")
        return redirect(url_for('user_page', username=username))

    slug = f"user:{username}"

    conn = get_db()
    c = conn.cursor()

    # garante que o "artigo" de usuário existe
    c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
    article = c.fetchone()
    if not article:
        timestamp = datetime.now().isoformat()
        c.execute("""
            INSERT INTO articles (slug, title, content, last_edited)
            VALUES (?, ?, ?, ?)
        """, (slug, f"Perfil de {username}", f"<p>Perfil de {username} criado.</p>", timestamp))
        conn.commit()
        c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
        article = c.fetchone()

    # cria o tópico
    c.execute("""
        INSERT INTO discussions (article_id, parent_id, topic_title, comment_text, user, ts)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (article['id'], None, topic_title if topic_title else None, comment_text, user, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    flash("Tópico criado com sucesso!", "success")
    return redirect(url_for('user_page', username=username))


@app.route('/user/<username>/discussion/<int:topic_id>/reply', methods=['POST'])
def reply_user_discussion(username, topic_id):
    cu = get_user()
    user = cu['username'] if cu else request.remote_addr
    comment_text = request.form.get('reply_text','').strip()
    reply_to = request.form.get('reply_to','').strip() or None

    if not comment_text:
        flash("Resposta vazia.", "error")
        return redirect(url_for('user_page', username=username))

    slug = f"user:{username}"
    conn = get_db()
    c = conn.cursor()

    # pega artigo de usuário
    c.execute("SELECT id FROM articles WHERE slug=?", (slug,))
    art = c.fetchone()
    if not art:
        flash("Perfil inexistente.", "error")
        conn.close()
        return redirect(url_for('home'))

    # garante que o tópico existe
    c.execute("SELECT id, user FROM discussions WHERE id=? AND article_id=? AND parent_id IS NULL", (topic_id, art['id']))
    topic = c.fetchone()
    if not topic:
        flash("Tópico inexistente.", "error")
        conn.close()
        return redirect(url_for('user_page', username=username))

    # insere reply
    c.execute("""
        INSERT INTO discussions (article_id, parent_id, topic_title, comment_text, user, reply_to, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (art['id'], topic_id, None, comment_text, user, reply_to, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    flash("Resposta adicionada!", "success")
    return redirect(url_for('user_page', username=username))

# ---------- AUTH ----------
# Registro seguro
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        if not username or not password:
            flash("Preenche aí.", "error")
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)  # hash da senha

        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
            conn.commit()
            flash("Conta criada! Faz login.", "success")
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash("Usuário já existe.", "error")

    return render_template("register.html", APP_TITLE=APP_TITLE, LICENSE=LICENSE)


# Login seguro
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        u = c.fetchone()
        conn.close()

        if u and check_password_hash(u['password'], password):
            session['username'] = u['username']
            flash("Logado!", "success")
            return redirect(url_for('home'))
        else:
            flash("Credenciais inválidas!", "error")

    return render_template("login.html", APP_TITLE=APP_TITLE, LICENSE=LICENSE)

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Saiu!", "success")
    return redirect(url_for('home'))

# ---------- SEARCH ----------
@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM articles WHERE title LIKE ? OR content LIKE ? LIMIT 50", ('%'+q+'%','%'+q+'%'))
    results = c.fetchall()
    conn.close()
    return render_template("search.html", APP_TITLE=APP_TITLE, cu=get_user(), title=f"Busca: {q}", q=q, results=results, LICENSE=LICENSE)

# ---------- STUBS / PAGES ----------
@app.route('/base')
def base():
    return render_template("base.html", LICENSE=LICENSE)

@app.route('/ajuda')
def ajuda():
    return render_template("simple.html", APP_TITLE=APP_TITLE, cu=get_user(), title="Ajuda", heading="Ajuda", text="Página de ajuda (stub).", LICENSE=LICENSE)

@app.route('/about')
def about():
    return render_template("simple.html", APP_TITLE=APP_TITLE, cu=get_user(), title="Sobre", heading="Sobre", text="Sobre o projeto Lusopédia (stub).", LICENSE=LICENSE)

@app.route('/portal')
def portal():
    return render_template("simple.html", APP_TITLE=APP_TITLE, cu=get_user(), title="Portal", heading="Portal", text="Portal (stub).", LICENSE=LICENSE)

@app.route('/afluentes/<path:slug>')
def afluentes(slug):
    return render_template("simple.html", APP_TITLE=APP_TITLE, cu=get_user(), title="Afluentes", heading=f"Afluentes de {slug}", text="Lista de afluentes (stub).", LICENSE=LICENSE)

@app.route('/recent_changes')
def recent_changes():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT a.title, h.ts, h.user
        FROM article_history h
        JOIN articles a ON a.slug = h.slug
        ORDER BY h.ts DESC
        LIMIT 50
    """)
    changes = c.fetchall()
    conn.close()
    return render_template(
        "recent.html",
        APP_TITLE=APP_TITLE,
        cu=get_user(),
        title="Alterações recentes",
        changes=changes,
        LICENSE=LICENSE
    )

@app.route('/Upload', methods=['GET', 'POST'])
def Upload():
    if request.method == 'POST':
        uploaded = request.files.get('file')
        filename = request.form.get('filename', '').strip()
        description = request.form.get('description', '').strip()

        # Sanitiza TUDO pra evitar XSS
        filename = sanitize_text(filename)
        description = sanitize_text(description)

        if not uploaded:
            flash("Nenhum arquivo enviado.", "error")
            return redirect(url_for('Upload'))

        if not filename:
            flash("O nome do ficheiro é obrigatório.", "error")
            return redirect(url_for('Upload'))

        # Garante extensão e nome seguro
        ext = os.path.splitext(uploaded.filename)[1]
        safe_filename = f"{uuid.uuid4().hex}{ext}"
        
        if not allowed_file(uploaded.filename):
            flash("Tipo de arquivo não permitido!", "error")
            return redirect(url_for('Upload'))

        path = os.path.join(UPLOAD_FOLDER, safe_filename)

        # Salva o arquivo na pasta
        uploaded.save(path)

        # Aqui tu salva descrição no banco, JSON, txt, sei lá
        # Exemplo cremoso:
        meta_path = os.path.join(UPLOAD_FOLDER, safe_filename + ".desc.txt")
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(description)

        flash("Arquivo enviado com sucesso.", "success")
        return redirect(url_for('Upload'))

    return render_template(
        "upload.html",
        APP_TITLE=APP_TITLE,
        cu=get_user(),
        title="Carregar ficheiro",
        LICENSE=LICENSE
    )

@app.route('/PagEspecial')
def PagEspecial():
    return render_template("simple.html", APP_TITLE=APP_TITLE, cu=get_user(), title="Páginas especiais", heading="Páginas especiais", text="Lista de páginas especiais (stub).", LICENSE=LICENSE)

@app.route('/profile/<username>')
def profile(username):
    cu = get_user()
    slug = f"user:{username}"

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
    article = c.fetchone()

    return render_template("user.html", APP_TITLE=APP_TITLE, cu=get_user(), title=f"Perfil de {username}", heading=f"Perfil: {username}", text="Página de perfil (stub).", LICENSE=LICENSE, article=article, username=cu['username'])

@app.route('/user/<username>', methods=['GET', 'POST'])
def user_page(username):
    cu = get_user()  # usuário logado, se houver
    slug = f"user:{username}"

    owner_name = slug.split(':',1)[1]

    conn = get_db()
    c = conn.cursor()

    # Pega ou cria o "artigo de usuário"
    c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
    article = c.fetchone()
    if not article:
        timestamp = datetime.now().isoformat()
        c.execute(
            "INSERT INTO articles (slug, title, content, last_edited) VALUES (?, ?, ?, ?)",
            (slug, f"Perfil de {username}", f"<p>Perfil de {username} criado.</p>", timestamp)
        )
        conn.commit()
        c.execute("SELECT * FROM articles WHERE slug=?", (slug,))
        article = c.fetchone()

    # verifica se o usuário logado é o dono do perfil
    is_owner = cu and cu['username'] == owner_name

    # processamento do POST
    if request.method == 'POST':
        if not is_owner:
            flash("Você não pode editar o perfil de outro usuário.", "error")
            conn.close()
            return redirect(url_for('user_page', username=username))

        new_content = request.form.get('content', '').strip()
        if new_content and new_content != article['content']:
            timestamp = datetime.now().isoformat()
            # salva versão antiga no histórico
            c.execute(
                "INSERT INTO article_history (slug, content, ts, user) VALUES (?, ?, ?, ?)",
                (slug, article['content'], timestamp, cu['username'])
            )
            # atualiza artigo
            c.execute(
                "UPDATE articles SET content=?, last_edited=?, last_editor=? WHERE slug=?",
                (new_content, timestamp, cu['username'], slug)
            )
            conn.commit()
            flash("Perfil atualizado com sucesso!", "success")

        conn.close()
        return redirect(url_for('user_page', username=username))

    # discussions principais (parent_id IS NULL)
    c.execute("SELECT * FROM discussions WHERE article_id=? AND parent_id IS NULL ORDER BY ts DESC", (article['id'],))
    discussion_topics = c.fetchall()

    # replies (parent_id NOT NULL)
    c.execute("SELECT * FROM discussions WHERE article_id=? AND parent_id IS NOT NULL ORDER BY ts ASC", (article['id'],))
    replies = c.fetchall()
    discussion_replies = {}
    for r in replies:
        discussion_replies.setdefault(r['parent_id'], []).append(r)

    conn.close()

    return render_template(
        'user.html',
        APP_TITLE=APP_TITLE,
        cu=cu,
        username=owner_name,
        article=article,
        slug=slug,
        discussion_topics=discussion_topics,
        discussion_replies=discussion_replies,
        is_owner=is_owner,  # passa para o template controlar o form
        LICENSE=LICENSE
    )

# Contribuições
@app.route('/contributions/<username>')
def contributions(username):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Puxa as edições feitas pelo usuário
    c.execute("""
        SELECT 
            h.id,
            h.slug,
            h.ts,
            h.user,
            a.title
        FROM article_history h
        LEFT JOIN articles a ON a.slug = h.slug
        WHERE h.user = ?
        ORDER BY h.ts DESC
        LIMIT 200
    """, (username,))

    contribs = c.fetchall()
    conn.close()

    return render_template(
        "contribs.html",
        APP_TITLE=APP_TITLE,
        cu=get_user(),
        title=f"Contribuições de {username}",
        contribs=contribs,
        LICENSE=LICENSE
    )

# Mostra histórico do artigo
@app.route('/history/<path:slug>')
def history(slug):
    db = sqlite3.connect(' DB_FILE')
    db.row_factory = sqlite3.Row
    cur = db.execute(
        "SELECT id, content, ts, user, summary FROM article_history WHERE slug = ? ORDER BY ts DESC",
        (slug,)
    )
    article_history = cur.fetchall()  # renomeado pra bater com o template
    db.close()

    # Pega título do artigo pra mostrar no cabeçalho
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT title FROM articles WHERE slug=?", (slug,))
    article = c.fetchone()
    conn.close()
    title = article['title'] if article else slug

    return render_template("article.html",
                           slug=slug,
                           title=title,
                           article_history=article_history,
                           LICENSE=LICENSE)

# Mostra uma versão específica
@app.route('/history/<path:slug>/<int:version_id>')
def view_version(slug, version_id):
    cu = get_user()
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Pega a versão exata
    cur.execute("SELECT * FROM article_history WHERE id = ?", (version_id,))
    version = cur.fetchone()
    if not version:
        conn.close()
        flash("Versão não encontrada.", "error")
        return redirect(url_for('goto', slug=slug))

    # Pega o título do artigo
    cur.execute("SELECT title FROM articles WHERE slug=?", (slug,))
    article = cur.fetchone()
    title = article['title'] if article else slug

    # Opcional: pegar histórico completo pra mostrar na tabela
    cur.execute("SELECT id, ts, user FROM article_history WHERE slug=? ORDER BY ts DESC", (slug,))
    article_history = cur.fetchall()

    conn.close()

    return render_template(
        "version.html",
        APP_TITLE=APP_TITLE,
        cu=cu,
        title=title,
        slug=slug,
        version=version,
        article_history=article_history,
        LICENSE=LICENSE
    )

@app.route('/privacy')
def privacy():
    return render_template("simple.html", APP_TITLE=APP_TITLE, cu=get_user(), title="Privacidade", heading="Política de privacidade", text="Política de privacidade (stub).", LICENSE=LICENSE)

@app.route('/terms')
def terms():
    return render_template("simple.html", APP_TITLE=APP_TITLE, cu=get_user(), title="Termos", heading="Termos de uso", text="Termos (stub).", LICENSE=LICENSE)

@app.route('/cookie_statement')
def cookie_statement():
    return render_template("simple.html", APP_TITLE=APP_TITLE, cu=get_user(), title="Cookies", heading="Cookies", text="Política de cookies (stub).", LICENSE=LICENSE)

# serve uploads
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------- START ----------
if __name__ == "__main__":
    init_db()
    app.run(ssl_context=('cert.pem', 'key.pem'), debug=False, host='0.0.0.0', port=5000)