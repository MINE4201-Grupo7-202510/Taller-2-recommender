import os

# --- Model Configuration ---
MODEL_DIR = "models"
SVD_MODEL_PATH = os.path.join(MODEL_DIR, "svd_model.pkl")
KNN_MODEL_PATH = os.path.join(MODEL_DIR, "knn_model.pkl")
DATASET_PATH = os.path.join(MODEL_DIR, "dataset.pkl")

# Best parameters for models
BEST_SVD_PARAMS = {
    'n_factors': 100,
    'reg_all': 0.02,
    'lr_all': 0.01
}

BEST_KNN_PARAMS = {
    'k': 20,
    'sim_options': {
        'name': 'cosine',
        'user_based': False
    }
}

# --- Database Configuration ---
# Read database credentials from environment variables for security
DB_USER = os.getenv("DB_USER", "user_yelp")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password1234")
DB_HOST = os.getenv("DB_HOST", "localhost") # Replace with your DB host if needed
DB_PORT = os.getenv("DB_PORT", "5432")     # Default PostgreSQL port
DB_NAME = os.getenv("DB_NAME", "db_yelp")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Recommendation Configuration ---
DEFAULT_TOP_N = 5
DEFAULT_W_KNN = 0.3
DEFAULT_W_SVD = 0.5
DEFAULT_W_CONTEXT = 0.2
MAX_ITEMS_TO_SCORE = 2000 # For explainable recommendations
MAX_ITEMS_TO_SCORE_QUICK = 1000 # For quick recommendations
NEUTRAL_SCORE = 3.0 # Default score for impossible predictions

# --- Logging Configuration ---
LOGGING_LEVEL = "INFO"
LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'