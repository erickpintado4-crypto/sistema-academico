from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import pandas as pd

app = Flask(__name__)
app.secret_key = "clave_IA"
USUARIO_LOGIN = "profesora"
PASSWORD_LOGIN = "1234"

DB_NAME = "notas.db"


def conectar():
    return sqlite3.connect(DB_NAME)


def crear_tablas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cursos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estudiantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        carrera TEXT NOT NULL,
        estado TEXT NOT NULL,
        curso_id INTEGER,
        FOREIGN KEY(curso_id) REFERENCES cursos(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evaluaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        ponderacion REAL NOT NULL,
        materia_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estudiante_id INTEGER NOT NULL,
        evaluacion_id INTEGER NOT NULL,
        nota REAL NOT NULL,
        observacion TEXT,
        FOREIGN KEY(estudiante_id) REFERENCES estudiantes(id),
        FOREIGN KEY(evaluacion_id) REFERENCES evaluaciones(id)
    )
    """)

    try:
        cursor.execute("ALTER TABLE estudiantes ADD COLUMN curso_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE evaluaciones ADD COLUMN materia_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE notas ADD COLUMN observacion TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE evaluaciones ADD COLUMN curso_id INTEGER")
    except sqlite3.OperationalError:
        pass

    cursor.execute("DELETE FROM cursos")

    cursos_predefinidos = ["A", "B", "C", "D"]

    for curso in cursos_predefinidos:
        cursor.execute(
            "INSERT OR IGNORE INTO cursos(nombre) VALUES (?)",
            (curso,)
        )

    conn.commit()
    conn.close()

@app.route("/", methods=["GET", "POST"])
def login():
    global USUARIO_LOGIN, PASSWORD_LOGIN

    mensaje = None

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "").strip()

        if usuario == USUARIO_LOGIN and password == PASSWORD_LOGIN:
            session["usuario"] = usuario
            return redirect("/dashboard")
        else:
            mensaje = "Usuario o contraseña incorrectos."

    return render_template(
        "login.html",
        mensaje=mensaje
    )


@app.route("/dashboard")
def dashboard():
    materia = request.args.get("materia", "")
    curso_id = request.args.get("curso_id", "")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT nombre FROM materias ORDER BY nombre")
    materias = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM cursos ORDER BY nombre")
    cursos = cursor.fetchall()

    consulta = """
    SELECT id, nombre, carrera, estado, curso_id
    FROM estudiantes
    WHERE 1=1
    """
    parametros = []

    if materia:
        consulta += " AND carrera = ?"
        parametros.append(materia)

    if curso_id:
        consulta += " AND curso_id = ?"
        parametros.append(curso_id)

    cursor.execute(consulta, parametros)
    estudiantes = cursor.fetchall()

    total_estudiantes = len(estudiantes)
    activos = sum(1 for e in estudiantes if e[3] == "Activo")
    bajas = sum(1 for e in estudiantes if e[3] == "Dado de baja")

    cursor.execute("SELECT COUNT(*) FROM evaluaciones")
    total_evaluaciones = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notas")
    total_notas = cursor.fetchone()[0]

    aprobados = 0
    reprobados = 0
    suma_promedios = 0

    for estudiante in estudiantes:
        estudiante_id = estudiante[0]

        cursor.execute("""
        SELECT SUM(notas.nota * evaluaciones.ponderacion / 100)
        FROM notas
        JOIN evaluaciones ON notas.evaluacion_id = evaluaciones.id
        WHERE notas.estudiante_id = ?
        """, (estudiante_id,))

        promedio = cursor.fetchone()[0] or 0
        suma_promedios += promedio

        if promedio >= 7:
            aprobados += 1
        else:
            reprobados += 1

    if total_estudiantes > 0:
        promedio_general = round(suma_promedios / total_estudiantes, 2)
    else:
        promedio_general = 0

    conn.close()

    return render_template(
        "dashboard.html",
        materias=materias,
        cursos=cursos,
        materia=materia,
        curso_id=curso_id,
        total_estudiantes=total_estudiantes,
        activos=activos,
        bajas=bajas,
        total_evaluaciones=total_evaluaciones,
        total_notas=total_notas,
        promedio_general=promedio_general,
        aprobados=aprobados,
        reprobados=reprobados
    )


@app.route("/estudiantes")
def estudiantes():
    busqueda = request.args.get("busqueda", "")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, nombre
    FROM cursos
    ORDER BY nombre
    """)
    cursos = cursor.fetchall()

    if busqueda:
        cursor.execute("""
        SELECT estudiantes.id,
               estudiantes.nombre,
               estudiantes.carrera,
               estudiantes.estado,
               cursos.nombre
        FROM estudiantes
        LEFT JOIN cursos
            ON estudiantes.curso_id = cursos.id
        WHERE estudiantes.nombre LIKE ?
           OR estudiantes.carrera LIKE ?
           OR estudiantes.estado LIKE ?
        ORDER BY estudiantes.id
        """, (
            f"%{busqueda}%",
            f"%{busqueda}%",
            f"%{busqueda}%"
        ))
    else:
        cursor.execute("""
        SELECT estudiantes.id,
               estudiantes.nombre,
               estudiantes.carrera,
               estudiantes.estado,
               cursos.nombre
        FROM estudiantes
        LEFT JOIN cursos
            ON estudiantes.curso_id = cursos.id
        ORDER BY estudiantes.id
        """)

    estudiantes = cursor.fetchall()

    conn.close()

    return render_template(
        "estudiantes.html",
        estudiantes=estudiantes,
        cursos=cursos,
        busqueda=busqueda
    )

@app.route("/agregar_estudiante", methods=["POST"])
def agregar_estudiante():
    nombre = request.form["nombre"]
    carrera = request.form["carrera"]
    estado = request.form["estado"]
    curso_id = request.form["curso_id"]

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO estudiantes(nombre, carrera, estado, curso_id)
    VALUES (?, ?, ?, ?)
    """, (nombre, carrera, estado, curso_id))

    conn.commit()
    conn.close()

    return redirect("/estudiantes")

@app.route("/evaluaciones")
def evaluaciones():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre FROM materias ORDER BY nombre")
    materias = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM cursos ORDER BY nombre")
    cursos = cursor.fetchall()

    cursor.execute("""
    SELECT evaluaciones.id,
           evaluaciones.nombre,
           evaluaciones.ponderacion,
           materias.nombre,
           cursos.nombre
    FROM evaluaciones
    LEFT JOIN materias ON evaluaciones.materia_id = materias.id
    LEFT JOIN cursos ON evaluaciones.curso_id = cursos.id
    ORDER BY materias.nombre, cursos.nombre
    """)
    evaluaciones = cursor.fetchall()

    cursor.execute("SELECT SUM(ponderacion) FROM evaluaciones")
    total = cursor.fetchone()[0] or 0

    conn.close()

    return render_template(
        "evaluaciones.html",
        evaluaciones=evaluaciones,
        materias=materias,
        cursos=cursos,
        total=total
    )


@app.route("/agregar_evaluacion", methods=["POST"])
def agregar_evaluacion():
    materia_id = request.form["materia_id"]
    curso_id = request.form["curso_id"]
    nombre = request.form["nombre"]
    ponderacion = float(request.form["ponderacion"])

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT SUM(ponderacion)
    FROM evaluaciones
    WHERE materia_id = ? AND curso_id = ?
    """, (materia_id, curso_id))

    total = cursor.fetchone()[0] or 0

    if total + ponderacion <= 100:
        cursor.execute("""
        INSERT INTO evaluaciones(nombre, ponderacion, materia_id, curso_id)
        VALUES (?, ?, ?, ?)
        """, (nombre, ponderacion, materia_id, curso_id))

    conn.commit()
    conn.close()

    return redirect("/evaluaciones")


@app.route("/notas")
def notas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT estudiantes.id,
           estudiantes.nombre,
           estudiantes.carrera,
           cursos.nombre
    FROM estudiantes
    LEFT JOIN cursos ON estudiantes.curso_id = cursos.id
    WHERE estudiantes.estado = 'Activo'
    ORDER BY estudiantes.nombre
    """)
    estudiantes = cursor.fetchall()

    cursor.execute("""
    SELECT evaluaciones.id,
           evaluaciones.nombre,
           materias.nombre,
           cursos.nombre
    FROM evaluaciones
    LEFT JOIN materias ON evaluaciones.materia_id = materias.id
    LEFT JOIN cursos ON evaluaciones.curso_id = cursos.id
    ORDER BY materias.nombre, cursos.nombre
    """)
    evaluaciones = cursor.fetchall()

    cursor.execute("""
    SELECT notas.id,
           estudiantes.nombre,
           estudiantes.carrera,
           cursos.nombre,
           evaluaciones.nombre,
           notas.nota,
           notas.observacion
    FROM notas
    JOIN estudiantes ON notas.estudiante_id = estudiantes.id
    JOIN evaluaciones ON notas.evaluacion_id = evaluaciones.id
    LEFT JOIN cursos ON estudiantes.curso_id = cursos.id
    ORDER BY notas.id
    """)
    notas = cursor.fetchall()

    conn.close()

    return render_template(
        "notas.html",
        estudiantes=estudiantes,
        evaluaciones=evaluaciones,
        notas=notas
    )


@app.route("/guardar_nota", methods=["POST"])
def guardar_nota():
    estudiante_id = int(request.form["estudiante_id"])
    evaluacion_id = int(request.form["evaluacion_id"])
    nota = float(request.form["nota"])
    observacion = request.form["observacion"]

    if 0 <= nota <= 10:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO notas(estudiante_id, evaluacion_id, nota, observacion)
        VALUES (?, ?, ?, ?)
        """, (estudiante_id, evaluacion_id, nota, observacion))

        conn.commit()
        conn.close()

    return redirect("/notas")

@app.route("/reportes")
def reportes():
    materia = request.args.get("materia", "")
    curso_id = request.args.get("curso_id", "")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT nombre FROM materias ORDER BY nombre")
    materias = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM cursos ORDER BY nombre")
    cursos = cursor.fetchall()

    cursor.execute("SELECT id, nombre, ponderacion FROM evaluaciones ORDER BY id")
    evaluaciones = cursor.fetchall()

    consulta = """
    SELECT estudiantes.id,
           estudiantes.nombre,
           estudiantes.carrera,
           estudiantes.estado,
           cursos.nombre
    FROM estudiantes
    LEFT JOIN cursos ON estudiantes.curso_id = cursos.id
    WHERE 1=1
    """

    parametros = []

    if materia:
        consulta += " AND estudiantes.carrera = ?"
        parametros.append(materia)

    if curso_id:
        consulta += " AND estudiantes.curso_id = ?"
        parametros.append(curso_id)

    consulta += " ORDER BY estudiantes.id"

    cursor.execute(consulta, parametros)
    estudiantes = cursor.fetchall()

    reporte_final = []

    for estudiante in estudiantes:
        estudiante_id = estudiante[0]

        fila = {
            "id": estudiante[0],
            "nombre": estudiante[1],
            "carrera": estudiante[2],
            "estado": estudiante[3],
            "curso": estudiante[4],
            "notas": [],
            "promedio": 0,
            "resultado": "",
            "observacion": ""
        }

        total = 0
        observacion_profesor = ""

        for evaluacion in evaluaciones:
            cursor.execute("""
            SELECT nota, observacion
            FROM notas
            WHERE estudiante_id = ? AND evaluacion_id = ?
            ORDER BY id DESC
            LIMIT 1
            """, (estudiante_id, evaluacion[0]))

            resultado = cursor.fetchone()

            if resultado:
                nota = resultado[0]
                observacion = resultado[1]
                fila["notas"].append(nota)
                total += nota * (evaluacion[2] / 100)

                if observacion:
                    observacion_profesor = observacion
            else:
                fila["notas"].append("-")

        fila["promedio"] = round(total, 2)

        if fila["estado"] == "Dado de baja":
            fila["resultado"] = "Baja"
            fila["observacion"] = observacion_profesor if observacion_profesor else "Estudiante dado de baja"
        elif fila["promedio"] >= 7:
            fila["resultado"] = "Aprobado"
            fila["observacion"] = observacion_profesor if observacion_profesor else "Cumple con la nota mínima"
        else:
            fila["resultado"] = "Reprobado"
            fila["observacion"] = observacion_profesor if observacion_profesor else "Requiere seguimiento académico"

        reporte_final.append(fila)

    conn.close()

    return render_template(
        "reportes.html",
        materias=materias,
        cursos=cursos,
        materia=materia,
        curso_id=curso_id,
        evaluaciones=evaluaciones,
        reporte_final=reporte_final
    )

@app.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    mensaje = None

    if request.method == "POST":
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        confirmar = request.form.get("confirmar", "")

        if actual == "" or nueva == "" or confirmar == "":
            mensaje = "Complete todos los campos."
        elif nueva != confirmar:
            mensaje = "La nueva contraseña no coincide."
        else:
            mensaje = "Contraseña actualizada correctamente."

    return render_template(
        "configuracion.html",
        mensaje=mensaje
    )

@app.route("/eliminar_evaluacion/<int:id>")
def eliminar_evaluacion(id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM notas WHERE evaluacion_id = ?", (id,))
    cursor.execute("DELETE FROM evaluaciones WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return redirect("/evaluaciones")


@app.route("/eliminar_nota/<int:id>")
def eliminar_nota(id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM notas WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return redirect("/notas")

@app.route("/exportar_excel")
def exportar_excel():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre, ponderacion FROM evaluaciones")
    evaluaciones = cursor.fetchall()

    cursor.execute("SELECT id, nombre, carrera, estado FROM estudiantes")
    estudiantes = cursor.fetchall()

    datos = []

    for estudiante in estudiantes:
        estudiante_id = estudiante[0]

        fila = {
            "ID": estudiante[0],
            "Estudiante": estudiante[1],
            "Carrera": estudiante[2],
            "Estado": estudiante[3]
        }

        total = 0

        for evaluacion in evaluaciones:
            cursor.execute("""
            SELECT nota FROM notas
            WHERE estudiante_id = ? AND evaluacion_id = ?
            """, (estudiante_id, evaluacion[0]))

            resultado = cursor.fetchone()

            if resultado:
                nota = resultado[0]
                fila[evaluacion[1]] = nota
                total += nota * (evaluacion[2] / 100)
            else:
                fila[evaluacion[1]] = "-"

        promedio = round(total, 2)
        fila["Promedio Final"] = promedio

        if estudiante[3] == "Dado de baja":
            fila["Resultado"] = "Baja"
            fila["Observación"] = "Estudiante dado de baja"
        elif promedio >= 7:
            fila["Resultado"] = "Aprobado"
            fila["Observación"] = "Cumple con la nota mínima"
        else:
            fila["Resultado"] = "Reprobado"
            fila["Observación"] = "Requiere seguimiento académico"

        datos.append(fila)

    conn.close()

    df = pd.DataFrame(datos)
    archivo = "reporte_calificaciones_detallado.xlsx"
    df.to_excel(archivo, index=False)

    return send_file(
        archivo,
        as_attachment=True,
        download_name="reporte_calificaciones_detallado.xlsx"
    )

@app.route("/enviar_reporte")
def enviar_reporte():
    asunto = "Reporte de calificaciones"
    cuerpo = "Adjunto el reporte de calificaciones generado por el sistema académico."

    enlace = (
        "mailto:?subject="
        + asunto.replace(" ", "%20")
        + "&body="
        + cuerpo.replace(" ", "%20")
    )

    return redirect(enlace)

@app.route("/dar_baja_estudiante/<int:id>")
def dar_baja_estudiante(id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE estudiantes SET estado = ? WHERE id = ?",
        ("Dado de baja", id)
    )

    conn.commit()
    conn.close()

    return redirect("/estudiantes")

@app.route("/editar_nota/<int:id>", methods=["GET", "POST"])
def editar_nota(id):
    conn = conectar()
    cursor = conn.cursor()

    if request.method == "POST":
        nueva_nota = float(request.form["nota"])

        if 0 <= nueva_nota <= 10:
            cursor.execute(
                "UPDATE notas SET nota = ? WHERE id = ?",
                (nueva_nota, id)
            )
            conn.commit()
            conn.close()
            return redirect("/notas")

    cursor.execute("""
    SELECT notas.id, estudiantes.nombre, evaluaciones.nombre, notas.nota
    FROM notas
    JOIN estudiantes ON notas.estudiante_id = estudiantes.id
    JOIN evaluaciones ON notas.evaluacion_id = evaluaciones.id
    WHERE notas.id = ?
    """, (id,))

    nota = cursor.fetchone()
    conn.close()

    return render_template("editar_nota.html", nota=nota)

@app.route("/reactivar_estudiante/<int:id>")
def reactivar_estudiante(id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE estudiantes SET estado = ? WHERE id = ?",
        ("Activo", id)
    )

    conn.commit()
    conn.close()

    return redirect("/estudiantes")

@app.route("/editar_estudiante/<int:id>", methods=["GET", "POST"])
def editar_estudiante(id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre FROM cursos ORDER BY nombre")
    cursos = cursor.fetchall()

    materias = [
        "Ciencias Políticas Primero",
        "Derecho Societario",
        "Derecho Minero",
        "Derecho Mercantil"
    ]

    if request.method == "POST":
        nombre = request.form["nombre"]
        carrera = request.form["carrera"]
        estado = request.form["estado"]
        curso_id = request.form["curso_id"]

        cursor.execute("""
        UPDATE estudiantes
        SET nombre = ?, carrera = ?, estado = ?, curso_id = ?
        WHERE id = ?
        """, (nombre, carrera, estado, curso_id, id))

        conn.commit()
        conn.close()

        return redirect("/estudiantes")

    cursor.execute("SELECT * FROM estudiantes WHERE id = ?", (id,))
    estudiante = cursor.fetchone()

    conn.close()

    return render_template(
        "editar_estudiante.html",
        estudiante=estudiante,
        cursos=cursos,
        materias=materias
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    crear_tablas()
    app.run(debug=True)