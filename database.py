from typing import Any, Dict, Optional
import pandas as pd
from sqlalchemy import create_engine, text, Engine
import traceback
import config
from utils import get_logger, get_day_period

logger = get_logger(__name__)

def create_db_engine() -> Optional[Engine]:
    """Creates the SQLAlchemy engine."""
    try:
        engine = create_engine(config.DATABASE_URL)
        # Test connection
        with engine.connect() as connection:
            logger.info(f"Successfully connected to database {config.DB_NAME} at {config.DB_HOST}:{config.DB_PORT}")
        return engine
    except Exception as e:
        logger.error(f"Failed to create database engine or connect: {e}")
        return None

def load_data(engine: Engine) -> Optional[pd.DataFrame]:
    """Load the datasets from the PostgreSQL database"""
    if engine is None:
        logger.error("Database engine is not initialized. Cannot load data.")
        return None

    logger.info("Loading datasets from PostgreSQL database...")
    try:
        # Define SQL queries for each table
        query_business = "SELECT * FROM business"
        query_review = "SELECT * FROM review"
        query_user = "SELECT * FROM yelp_user" # Use correct table name

        # Load dataframes from database tables using the provided engine
        with engine.connect() as connection:
            df_business = pd.read_sql_query(sql=text(query_business), con=connection)
            df_review = pd.read_sql_query(sql=text(query_review), con=connection)
            df_user = pd.read_sql_query(sql=text(query_user), con=connection)


        logger.info(f"Loaded {len(df_business)} businesses, {len(df_review)} reviews, {len(df_user)} users.")

        # --- Data Preprocessing and Renaming ---
        df_review.rename(columns={
            'stars': 'stars_review', 'useful': 'useful_review',
            'funny': 'funny_review', 'cool': 'cool_review'
        }, inplace=True)
        df_user.rename(columns={
            'name': 'name_user', 'review_count': 'review_count_user',
            'useful': 'useful_user', 'funny': 'funny_user', 'cool': 'cool_user'
        }, inplace=True)

        # Merge dataframes
        df_merged = pd.merge(df_review, df_business, on='business_id', how='left')
        logger.info(f"Shape after merging reviews and businesses: {df_merged.shape}")
        df = pd.merge(df_merged, df_user, on='user_id', how='left')
        logger.info(f"Shape after merging with users: {df.shape}")

        # Ensure 'date' column is datetime type
        df['date'] = pd.to_datetime(df['date'])

        # Add contextual features
        df['hour'] = df['date'].dt.hour
        df['day_of_week'] = df['date'].dt.day_name()
        df['day_period'] = df['hour'].apply(get_day_period)

        # Handle potential NaN values after merges if necessary
        # df.fillna({'some_column': default_value}, inplace=True)

        logger.info("Data loaded and merged successfully from database")
        logger.info(f"Final DataFrame columns: {df.columns.tolist()}")
        logger.info(f"Final DataFrame shape: {df.shape}")
        return df

    except Exception as e:
        logger.error(f"Error loading data from database: {str(e)}")
        traceback.print_exc()
        return None

def get_user_profile_and_history(engine: Engine, df: pd.DataFrame, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetches user profile and rating history."""
    if df is None:
        logger.warning("DataFrame not available for fetching user history.")
        # Try fetching profile directly from DB if df is missing
        try:
            with engine.connect() as connection:
                profile_query = text("""
                    SELECT user_id, name as name_user, review_count as review_count_user,
                           yelping_since, average_stars, useful as useful_user, funny as funny_user,
                           cool as cool_user, fans, elite, friends
                    FROM yelp_user WHERE user_id = :user_id
                """)
                profile_result = connection.execute(profile_query, {'user_id': user_id}).mappings().first()
                if profile_result:
                    profile_dict = dict(profile_result)
                    if 'yelping_since' in profile_dict and pd.notna(profile_dict['yelping_since']):
                         profile_dict['yelping_since'] = profile_dict['yelping_since'].isoformat()
                    return {
                        "user_id": user_id,
                        "profile": profile_dict,
                        "ratings": [] # No ratings from df
                    }
                else:
                    return None # User not found in DB either
        except Exception as e:
            logger.error(f"Database error fetching profile for user {user_id}: {e}")
            return None # Indicate error or inability to fetch

    # Filter user data from the main DataFrame
    user_data = df[df['user_id'] == user_id]

    if user_data.empty:
        # User exists in df index but has no rows? Unlikely with merge, but check DB.
        # Or user genuinely not in the loaded review data. Check DB for profile.
        try:
            with engine.connect() as connection:
                profile_query = text("""
                    SELECT user_id, name as name_user, review_count as review_count_user,
                           yelping_since, average_stars, useful as useful_user, funny as funny_user,
                           cool as cool_user, fans, elite, friends
                    FROM yelp_user WHERE user_id = :user_id
                """)
                profile_result = connection.execute(profile_query, {'user_id': user_id}).mappings().first()
                if profile_result:
                    profile_dict = dict(profile_result)
                    if 'yelping_since' in profile_dict and pd.notna(profile_dict['yelping_since']):
                         profile_dict['yelping_since'] = profile_dict['yelping_since'].isoformat()
                    return {
                        "user_id": user_id,
                        "profile": profile_dict,
                        "ratings": [] # No ratings found in the review data used
                    }
                else:
                    return None # User not found
        except Exception as e:
            logger.error(f"Database error checking user {user_id}: {e}")
            return None # Indicate error

    # Get user's ratings history from the filtered data
    ratings = user_data[['business_id', 'name', 'stars_review', 'date']] \
              .rename(columns={'name': 'business_name', 'stars_review': 'rating_given'}) \
              .to_dict('records')

    # Get user profile information
    profile_cols = [
        'name_user', 'review_count_user', 'yelping_since', 'average_stars',
        'useful_user', 'funny_user', 'cool_user', 'fans', 'elite', 'friends'
    ]
    # Ensure columns exist before accessing
    valid_profile_cols = [col for col in profile_cols if col in user_data.columns]
    profile_info = user_data[valid_profile_cols].iloc[0].to_dict()

    # Convert timestamp/datetime to string for JSON compatibility
    if 'yelping_since' in profile_info and pd.notna(profile_info['yelping_since']):
        profile_info['yelping_since'] = profile_info['yelping_since'].isoformat()
    for r in ratings:
        if 'date' in r and pd.notna(r['date']):
             r['date'] = r['date'].isoformat()

    return {
        "user_id": user_id,
        "profile": profile_info,
        "ratings": ratings
    }