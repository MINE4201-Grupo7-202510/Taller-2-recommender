**FastAPI Yelp Project**

Este repositorio contiene un proyecto de FastAPI que interactúa con una base de datos PostgreSQL para almacenar información de negocios, usuarios, reseñas y fotos al estilo Yelp. A continuación se describe cómo configurar y ejecutar el proyecto desde cero.

---

## 🔧 Requisitos Previos

* **Python 3.9+** instalado en tu sistema. Puedes verificar la versión con:

  ```bash
  python --version
  ```
* **PostgreSQL** instalado y corriendo (versión 12 o superior recomendada).
* **Git** (opcional, para clonar el repositorio).

---

## 📁 Clonar el Repositorio

Si no tienes el código localmente, clónalo usando Git:

```bash
git clone https://github.com/tu-usuario/fastapi-yelp.git
cd fastapi-yelp
```

Alternativamente, descarga el ZIP y extrae el contenido.

---

## 🗄️ Crear la Base de Datos PostgreSQL

1. Conéctate a PostgreSQL usando tu cliente preferido (psql, pgAdmin, etc.).

2. Ejecuta los siguientes comandos para crear el usuario y la base de datos:

   ```sql
   -- 1. Crear usuario y base de datos
   CREATE USER user_yelp WITH PASSWORD 'password1234';
   CREATE DATABASE db_yelp OWNER user_yelp;

   -- 2. Conectarse a la nueva base de datos
   \c db_yelp

   -- 3. Ajustar codificación
   \encoding UTF8
   ALTER DATABASE db_yelp SET client_encoding TO 'UTF8';
   ```

3. Crea las tablas necesarias ejecutando este bloque SQL:

   ```sql
   -- Tabla business
   DROP TABLE IF EXISTS business CASCADE;
   CREATE TABLE business (
     business_id TEXT PRIMARY KEY,
     name TEXT,
     address TEXT,
     city TEXT,
     state TEXT,
     postal_code TEXT,
     latitude NUMERIC,
     longitude NUMERIC,
     stars NUMERIC,
     review_count INTEGER,
     is_open BOOLEAN,
     attributes JSONB,
     categories TEXT,
     hours JSONB
   );

   -- Tabla yelp_user
   DROP TABLE IF EXISTS yelp_user CASCADE;
   CREATE TABLE yelp_user (
     user_id TEXT PRIMARY KEY,
     name TEXT,
     review_count INTEGER,
     yelping_since TIMESTAMP,
     useful INTEGER,
     funny INTEGER,
     cool INTEGER,
     elite TEXT,
     friends TEXT,
     fans INTEGER,
     average_stars NUMERIC,
     compliment_hot INTEGER,
     compliment_more INTEGER,
     compliment_profile INTEGER,
     compliment_cute INTEGER,
     compliment_list INTEGER,
     compliment_note INTEGER,
     compliment_plain INTEGER,
     compliment_cool INTEGER,
     compliment_funny INTEGER,
     compliment_writer INTEGER,
     compliment_photos INTEGER
   );

   -- Tabla review
   DROP TABLE IF EXISTS review CASCADE;
   CREATE TABLE review (
     review_id TEXT PRIMARY KEY,
     user_id TEXT REFERENCES yelp_user(user_id),
     business_id TEXT REFERENCES business(business_id),
     stars NUMERIC,
     useful INTEGER,
     funny INTEGER,
     cool INTEGER,
     text TEXT,
     date TIMESTAMP
   );

   -- Tabla photo
   DROP TABLE IF EXISTS photo CASCADE;
   CREATE TABLE photo (
     photo_id TEXT PRIMARY KEY,
     business_id TEXT REFERENCES business(business_id),
     caption TEXT,
     label TEXT
   );
   ```

4. Otorga permisos al usuario `user_yelp`:

   ```sql
   -- Permisos en tablas, secuencias y base de datos
   GRANT ALL PRIVILEGES ON DATABASE db_yelp TO user_yelp;
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO user_yelp;
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO user_yelp;
   ```

5. Verifica la creación:

   ```sql
   SELECT * FROM yelp_user;
   SELECT * FROM business;
   SELECT * FROM review;
   SELECT * FROM photo;
   ```

---

## 🌐 Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con el siguiente contenido:

```ini
DB_USER="user_yelp"
DB_PASSWORD="password1234"
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="db_yelp"
```

> Asegúrate de no subir tu `.env` a repositorios públicos.

---

## 📦 Instalación de Dependencias

1. Crea y activa un entorno virtual (recomendado):

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate   # Windows
   ```

2. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Cargar Datos de Ejemplo

Para poblar la base de datos con datos de Yelp, ejecuta los scripts:

```bash
python upload_database_data.py
python upload_database_data_photo.py
```

Estos scripts leerán archivos JSON/CSV y cargarán los datos en las tablas correspondientes.

---

## 🚀 Ejecutar el Servidor

Inicia la aplicación FastAPI con Uvicorn:

```bash
uvicorn main:app --reload
```

* La opción `--reload` detecta cambios en el código y reinicia el servidor automáticamente.
* Por defecto, el servidor se ejecuta en `http://127.0.0.1:8000`.

---

## 📖 Documentación Interactiva

Una vez en marcha, accede a la documentación automática de la API en:

* Swagger UI: `http://127.0.0.1:8000/docs`
* ReDoc: `http://127.0.0.1:8000/redoc`

---

## 🛠️ Estructura del Proyecto

```
fastapi-yelp/
├── main.py               # Punto de entrada de la aplicación
├── routers/              # Endpoints de la API
├── models/               # Definición de modelos Pydantic y SQLAlchemy
├── database.py           # Conexión y sesión con PostgreSQL
├── upload_database_data.py       # Script de carga de datos principal
├── upload_database_data_photo.py # Script de carga de fotos
├── requirements.txt      # Dependencias del proyecto
└── .env                  # Variables de entorno (no versionar)
```

---
