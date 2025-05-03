import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine
import ast

# 1. Conexión a la base de datos
db_user = 'user_yelp'

# Ajusta la contraseña y host/puerto según tu configuración:
db_pass = 'password1234'
db_host = 'localhost'
db_port = '5432'
db_name = 'db_yelp'
engine = create_engine(f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}')

# 2. Leer CSVs en DataFrames
df_business = pd.read_csv('data/business.csv', dtype={'business_id': str})
df_user     = pd.read_csv('data/user.csv',     dtype={'user_id': str})
df_review   = pd.read_csv('data/review.csv',   dtype={'review_id': str})

# 3. Convertir columnas JSON y tipos
# Convertir atributos de string a dict
df_business['attributes'] = df_business['attributes'].apply(lambda x: ast.literal_eval(x) if pd.notnull(x) else {})
df_business['hours']      = df_business['hours'].apply(lambda x: ast.literal_eval(x) if pd.notnull(x) else {})
# Convertir is_open de integer a boolean
df_business['is_open']    = df_business['is_open'].astype(bool)

# 4. Cargar en la BD
print('Cargando tabla business...')
df_business.to_sql(
    'business', engine,
    if_exists='append',
    index=False,
    dtype={
        'attributes': sqlalchemy.types.JSON(),
        'hours':      sqlalchemy.types.JSON()
    }
)

print('Cargando tabla yelp_user...')
df_user.to_sql('yelp_user', engine, if_exists='append', index=False)

print('Cargando tabla review...')
df_review.to_sql('review', engine, if_exists='append', index=False)

print('¡Carga completada!')