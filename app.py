from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import os
from datetime import datetime

# Configuración de Flask con templates en java/templates
app = Flask(__name__, template_folder='java/templates', static_folder='static')
app.secret_key = "seguridad_ferrestock_2025"

# ========== CONFIGURACIÓN DE BASE DE DATOS ==========

DB_PATH = "ferrestock.db"

def conectar():
    """Abre una conexión a la base de datos SQLite"""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
    return con

def init_db():
    """Crea las tablas de la base de datos con estructura mejorada"""
    con = conectar()
    cur = con.cursor()
    
    # ===== TABLA DE USUARIOS =====
    # Almacena usuarios del sistema con roles
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'usuario',
            estado TEXT DEFAULT 'activo',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ===== TABLA DE CATEGORÍAS =====
    # Categorías de productos (Herrajes, Tuberías, Eléctrico, etc.)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categorias(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            descripcion TEXT
        )
    """)
    
    # ===== TABLA DE PRODUCTOS =====
    # Catálogo de productos disponibles
    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria_id INTEGER,
            descripcion TEXT,
            precio REAL DEFAULT 0,
            sku TEXT UNIQUE,
            estado TEXT DEFAULT 'activo',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(categoria_id) REFERENCES categorias(id)
        )
    """)
    
    # ===== TABLA DE STOCK =====
    # Inventario de productos con cantidad y ubicación física
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER DEFAULT 0,
            ubicacion TEXT,
            cantidad_minima INTEGER DEFAULT 10,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(producto_id) REFERENCES productos(id)
        )
    """)
    
    # ===== TABLA DE INVENTARIO =====
    # Detalle de ubicación y estado de productos en almacén
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventario(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            ubicacion TEXT,
            cantidad INTEGER,
            observaciones TEXT,
            ultima_revision TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(stock_id) REFERENCES stock(id)
        )
    """)
    
    # ===== TABLA DE MOVIMIENTOS =====
    # Historial de cambios en el stock
    cur.execute("""
        CREATE TABLE IF NOT EXISTS movimientos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            tipo TEXT,
            cantidad INTEGER,
            usuario_id INTEGER,
            descripcion TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(stock_id) REFERENCES stock(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)
    
    # Crear usuario admin por defecto
    cur.execute("SELECT * FROM usuarios WHERE usuario=?", ("admin",))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO usuarios (usuario, clave, nombre, rol) 
               VALUES (?, ?, ?, ?)""",
            ("admin", "admin123", "Administrador", "admin")
        )
    
    # Insertar categorías por defecto si no existen
    categorias = ["Herrajes", "Tuberías", "Eléctrico", "Herramientas", "Pinturas"]
    for cat in categorias:
        cur.execute("SELECT * FROM categorias WHERE nombre=?", (cat,))
        if not cur.fetchone():
            cur.execute("INSERT INTO categorias (nombre) VALUES (?)", (cat,))
    
    con.commit()
    con.close()

# Inicializar BD al arrancar la aplicación
if not os.path.exists(DB_PATH):
    init_db()
else:
    # Verificar que las tablas existan, si no, crearlas
    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    if not cur.fetchall():
        con.close()
        os.remove(DB_PATH)
        init_db()
    else:
        con.close()

# ========== RUTAS PÚBLICAS - AUTENTICACIÓN ==========

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    """Página de login - autentica usuarios contra la BD"""
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "").strip()

        if not usuario or not clave:
            return render_template("login.html", error="Complete todos los campos")

        con = conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT id, nombre, rol FROM usuarios 
            WHERE usuario=? AND clave=? AND estado='activo'
        """, (usuario, clave))
        resultado = cur.fetchone()
        con.close()

        if resultado:
            # Guardar sesión si credenciales son válidas
            session["usuario_id"] = resultado["id"]
            session["usuario"] = usuario
            session["nombre"] = resultado["nombre"]
            session["rol"] = resultado["rol"]
            return redirect("/base")
        else:
            # Las credenciales son inválidas
            return render_template("login.html", error="Usuario o contraseña incorrectos")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Cierra la sesión del usuario"""
    session.clear()
    return redirect("/")

@app.route('/base')
def base_page():
    """Página principal después del login"""
    # Pasar el rol a la plantilla
    rol = session.get('rol', 'visitante')
    nombre = session.get('nombre', '')
    return render_template('base.html', rol=rol, nombre=nombre)

@app.route('/contacto')
def contacto_page():
    """Página de contacto"""
    return render_template('Contacto.html')

@app.route('/productos')
def productos_page():
    """Página de productos"""
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT p.id, p.nombre, p.descripcion, p.precio, c.nombre as categoria
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.estado='activo'
    """)
    items = cur.fetchall()
    con.close()
    
    return render_template('productos.html', productos=items)

# ========== RUTAS PROTEGIDAS (SOLO ADMIN) ==========

@app.route('/stock')
def stock_page():
    """Página de stock - solo acceso admin"""
    if session.get('rol') != 'admin':
        return redirect('/base')
    
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT s.id, p.nombre, c.nombre as categoria, s.ubicacion, s.cantidad, s.cantidad_minima
        FROM stock s
        JOIN productos p ON s.producto_id = p.id
        LEFT JOIN categorias c ON p.categoria_id = c.id
    """)
    items = cur.fetchall()
    con.close()
    
    return render_template('stock.html', stock=items)

@app.route('/inventario')
def inventario_page():
    """Página de inventario - solo acceso admin"""
    if session.get('rol') != 'admin':
        return redirect('/base')
    
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT i.id, p.nombre, c.nombre as categoria, s.ubicacion, s.cantidad
        FROM inventario i
        JOIN stock s ON i.stock_id = s.id
        JOIN productos p ON s.producto_id = p.id
        LEFT JOIN categorias c ON p.categoria_id = c.id
    """)
    items = cur.fetchall()
    con.close()
    
    return render_template('inventario.html', inventario=items)

# ========== API ROUTES - STOCK (JSON) ==========

@app.route('/api/stock', methods=['GET'])
def api_get_stock():
    """Obtener todos los productos en stock"""
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT s.id, p.nombre as producto, c.nombre as categoria, 
               s.ubicacion, s.cantidad
        FROM stock s
        JOIN productos p ON s.producto_id = p.id
        LEFT JOIN categorias c ON p.categoria_id = c.id
    """)
    items = [dict(row) for row in cur.fetchall()]
    con.close()
    
    return jsonify(items)

@app.route('/api/stock', methods=['POST'])
def api_crear_stock():
    """Crear nuevo item en stock"""
    if session.get('rol') != 'admin':
        return jsonify({"error": "No autorizado"}), 403
    
    data = request.get_json()
    
    con = conectar()
    cur = con.cursor()
    
    try:
        # Crear producto si no existe
        cur.execute("SELECT id FROM productos WHERE nombre=?", (data['producto'],))
        prod = cur.fetchone()
        
        if not prod:
            cur.execute(
                "INSERT INTO productos (nombre, categoria_id) VALUES (?, ?)",
                (data['producto'], 1)  # categoría por defecto
            )
            producto_id = cur.lastrowid
        else:
            producto_id = prod[0]
        
        # Crear stock
        cur.execute("""
            INSERT INTO stock (producto_id, cantidad, ubicacion)
            VALUES (?, ?, ?)
        """, (producto_id, data['cantidad'], data['ubicacion']))
        
        con.commit()
        return jsonify({"success": True, "id": cur.lastrowid})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        con.close()

@app.route('/api/stock/<int:stock_id>', methods=['PUT'])
def api_actualizar_stock(stock_id):
    """Actualizar un item en stock"""
    if session.get('rol') != 'admin':
        return jsonify({"error": "No autorizado"}), 403
    
    data = request.get_json()
    
    con = conectar()
    cur = con.cursor()
    
    try:
        cur.execute("""
            UPDATE stock 
            SET cantidad=?, ubicacion=?, fecha_actualizacion=CURRENT_TIMESTAMP
            WHERE id=?
        """, (data['cantidad'], data['ubicacion'], stock_id))
        
        con.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        con.close()

@app.route('/api/stock/<int:stock_id>', methods=['DELETE'])
def api_eliminar_stock(stock_id):
    """Eliminar un item del stock"""
    if session.get('rol') != 'admin':
        return jsonify({"error": "No autorizado"}), 403
    
    con = conectar()
    cur = con.cursor()
    
    try:
        # Eliminar primero los items del inventario relacionados
        cur.execute("DELETE FROM inventario WHERE stock_id=?", (stock_id,))
        # Luego eliminar el stock
        cur.execute("DELETE FROM stock WHERE id=?", (stock_id,))
        
        con.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        con.close()

# ========== API ROUTES - INVENTARIO (JSON) ==========

@app.route('/api/inventario', methods=['GET'])
def api_get_inventario():
    """Obtener todos los items del inventario"""
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT i.id, p.nombre as producto, c.nombre as categoria, 
               i.ubicacion, s.cantidad
        FROM inventario i
        JOIN stock s ON i.stock_id = s.id
        JOIN productos p ON s.producto_id = p.id
        LEFT JOIN categorias c ON p.categoria_id = c.id
    """)
    items = [dict(row) for row in cur.fetchall()]
    con.close()
    
    return jsonify(items)

@app.route('/api/inventario', methods=['POST'])
def api_crear_inventario():
    """Crear nuevo item en inventario"""
    if session.get('rol') != 'admin':
        return jsonify({"error": "No autorizado"}), 403
    
    data = request.get_json()
    
    con = conectar()
    cur = con.cursor()
    
    try:
        # Verificar que el stock existe
        cur.execute("SELECT id, cantidad FROM stock WHERE id=?", (data['stock_id'],))
        stock = cur.fetchone()
        
        if not stock:
            return jsonify({"error": "Stock no encontrado"}), 404
        
        # Crear inventario
        cur.execute("""
            INSERT INTO inventario (stock_id, ubicacion, cantidad, observaciones)
            VALUES (?, ?, ?, ?)
        """, (data['stock_id'], data['ubicacion'], stock[1], data.get('observaciones', '')))
        
        con.commit()
        return jsonify({"success": True, "id": cur.lastrowid})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        con.close()

@app.route('/api/inventario/<int:inv_id>', methods=['PUT'])
def api_actualizar_inventario(inv_id):
    """Actualizar un item en inventario"""
    if session.get('rol') != 'admin':
        return jsonify({"error": "No autorizado"}), 403
    
    data = request.get_json()
    
    con = conectar()
    cur = con.cursor()
    
    try:
        cur.execute("""
            UPDATE inventario 
            SET ubicacion=?, observaciones=?, ultima_revision=CURRENT_TIMESTAMP
            WHERE id=?
        """, (data['ubicacion'], data.get('observaciones', ''), inv_id))
        
        con.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        con.close()

@app.route('/api/inventario/<int:inv_id>', methods=['DELETE'])
def api_eliminar_inventario(inv_id):
    """Eliminar un item del inventario"""
    if session.get('rol') != 'admin':
        return jsonify({"error": "No autorizado"}), 403
    
    con = conectar()
    cur = con.cursor()
    
    try:
        cur.execute("DELETE FROM inventario WHERE id=?", (inv_id,))
        con.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        con.close()

# ========== API ROUTES - USUARIOS (JSON) ==========

@app.route('/api/usuarios', methods=['GET'])
def api_get_usuarios():
    """Obtener todos los usuarios (solo admin)"""
    if session.get('rol') != 'admin':
        return jsonify({"error": "No autorizado"}), 403
    
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT id, usuario, nombre, rol, estado, fecha_creacion
        FROM usuarios
    """)
    items = [dict(row) for row in cur.fetchall()]
    con.close()
    
    return jsonify(items)

@app.route('/api/usuarios', methods=['POST'])
def api_crear_usuario():
    """Crear nuevo usuario"""
    data = request.get_json()
    
    con = conectar()
    cur = con.cursor()
    
    try:
        cur.execute("""
            INSERT INTO usuarios (usuario, clave, nombre, rol)
            VALUES (?, ?, ?, ?)
        """, (data['usuario'], data['clave'], data['nombre'], data.get('rol', 'usuario')))
        
        con.commit()
        return jsonify({"success": True, "id": cur.lastrowid})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Usuario ya existe"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        con.close()

# ========== MANEJO DE ERRORES ==========

@app.errorhandler(404)
def no_encontrado(error):
    """Maneja rutas no encontradas"""
    return redirect('/base'), 404

@app.errorhandler(500)
def error_servidor(error):
    """Maneja errores del servidor"""
    return "Error interno del servidor", 500

@app.errorhandler(403)
def acceso_denegado(error):
    """Maneja acceso denegado"""
    return redirect('/base'), 403

# ========== INICIAR APLICACIÓN ==========

if __name__ == '__main__':
    # Ejecutar en modo debug para desarrollo
    # Cambiar debug=False en producción
    app.run(debug=True, host='localhost', port=5000)
