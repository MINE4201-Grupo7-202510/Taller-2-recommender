import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
import sys # Import sys to use sys.exit

# 1. Conexión a la base de datos (ajusta si es necesario)
db_user = 'user_yelp'
db_pass = 'password1234'
db_host = 'localhost'
db_port = '5432'
db_name = 'db_yelp'

try:
    engine = create_engine(f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}')
    # Test connection
    with engine.connect() as connection:
        print("Conexión a la base de datos exitosa.")
except Exception as e:
    print(f"Error al conectar a la base de datos: {e}")
    sys.exit(1) # Exit if connection fails

# 2. Leer photo.json en un DataFrame
print('Leyendo photo.json...')
try:
    df_photo = pd.read_json('data/photos.json', lines=True, dtype={'photo_id': str, 'business_id': str})
    print(f"Leídos {len(df_photo)} registros de photo.json.")
except ValueError as e:
    print(f"Error al leer photo.json: {e}")
    print("Asegúrate de que el archivo 'data/photo.json' existe y contiene un JSON válido por línea.")
    sys.exit(1)
except FileNotFoundError:
    print("Error: No se encontró el archivo 'data/photo.json'.")
    sys.exit(1)
except Exception as e:
    print(f"Ocurrió un error inesperado al leer photo.json: {e}")
    sys.exit(1)


# 3. Obtener business_id existentes de la tabla business
print('Obteniendo business_id existentes de la tabla business...')
try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT business_id FROM business"))
        existing_business_ids = {row[0] for row in result}
    print(f"Encontrados {len(existing_business_ids)} business_id existentes.")
    if not existing_business_ids:
        print("Advertencia: No se encontraron business_id en la tabla 'business'. No se cargarán fotos.")
        sys.exit(0) # Exit gracefully if no businesses exist
except Exception as e:
    print(f"Error al obtener business_id de la tabla business: {e}")
    sys.exit(1)

# 4. Filtrar el DataFrame de fotos
original_count = len(df_photo)
df_photo_filtered = df_photo[df_photo['business_id'].isin(existing_business_ids)].copy()
filtered_count = len(df_photo_filtered)
skipped_count = original_count - filtered_count
print(f"Filtrando fotos: {filtered_count} fotos tienen un business_id válido.")
if skipped_count > 0:
    print(f"Se omitirán {skipped_count} fotos debido a business_id no encontrado en la tabla 'business'.")

# 5. Cargar datos filtrados en la BD
if not df_photo_filtered.empty:
    print('Cargando tabla photo con datos filtrados...')
    try:
        df_photo_filtered.to_sql(
            'photo',
            engine,
            if_exists='append',
            index=False,
            chunksize=10000 # Opcional: procesar en lotes para archivos grandes
        )
        print(f'¡Carga de {filtered_count} registros en la tabla photo completada!')
    except Exception as e:
        print(f"Error al cargar datos filtrados en la tabla photo: {e}")
        sys.exit(1)
else:
    print("No hay fotos válidas para cargar después del filtrado.")

print("Proceso finalizado.")