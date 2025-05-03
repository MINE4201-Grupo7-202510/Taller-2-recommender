import pandas as pd
import numpy as np
import os
import pickle
import traceback
from typing import Optional, Tuple, List, Dict, Any
from surprise import Reader, Dataset, SVD, KNNBasic
from surprise.model_selection import train_test_split
from surprise.trainset import Trainset
from concurrent.futures import ThreadPoolExecutor

import config
from utils import ensure_model_dir, get_logger

logger = get_logger(__name__)

# Type hints for models
SVDModelType = Optional[SVD]
KNNModelType = Optional[KNNBasic]
TrainsetType = Optional[Trainset]
TestsetType = Any # Testset is usually a list of tuples

def prepare_surprise_dataset(df: pd.DataFrame) -> Optional[Tuple[TrainsetType, TestsetType]]:
    """Prepare dataset for Surprise library"""
    if df is None or df.empty:
        logger.error("DataFrame is empty or not loaded. Cannot prepare Surprise dataset.")
        return None

    required_cols = ['user_id', 'business_id', 'stars_review']
    if not all(col in df.columns for col in required_cols):
        logger.error(f"Missing one or more required columns {required_cols} in the DataFrame.")
        logger.error(f"Available columns: {df.columns.tolist()}")
        return None

    logger.info("Preparing Surprise dataset...")
    try:
        df_surprise = df[required_cols].copy()
        df_surprise['stars_review'] = pd.to_numeric(df_surprise['stars_review'], errors='coerce')
        df_surprise.dropna(subset=['stars_review'], inplace=True)

        if df_surprise.empty:
             logger.error("No valid rating data available after cleaning for Surprise.")
             return None

        min_rating = df_surprise['stars_review'].min()
        max_rating = df_surprise['stars_review'].max()
        logger.info(f"Rating scale for Surprise: ({min_rating}, {max_rating})")

        reader = Reader(rating_scale=(min_rating, max_rating))
        data = Dataset.load_from_df(df_surprise[['user_id', 'business_id', 'stars_review']], reader)
        train_set, test_set = train_test_split(data, test_size=0.2, random_state=42)

        # Save the dataset
        ensure_model_dir()
        with open(config.DATASET_PATH, 'wb') as f:
            pickle.dump((train_set, test_set), f)

        logger.info("Surprise dataset prepared successfully")
        return train_set, test_set
    except Exception as e:
        logger.error(f"Error preparing Surprise dataset: {str(e)}")
        traceback.print_exc()
        return None

def load_or_train_models(df: pd.DataFrame) -> Tuple[SVDModelType, KNNModelType, TrainsetType, TestsetType]:
    """Load models from disk or train new ones."""
    ensure_model_dir()
    svd_model: SVDModelType = None
    knn_model: KNNModelType = None
    train_set: TrainsetType = None
    test_set: TestsetType = None

    # Load or prepare dataset
    if os.path.exists(config.DATASET_PATH):
        logger.info("Loading existing dataset...")
        try:
            with open(config.DATASET_PATH, 'rb') as f:
                train_set, test_set = pickle.load(f)
        except Exception as e:
             logger.error(f"Error loading dataset from pickle: {e}. Attempting to regenerate.")
             dataset_result = prepare_surprise_dataset(df)
             if dataset_result:
                 train_set, test_set = dataset_result
    else:
        logger.info("Dataset not found. Preparing from loaded data...")
        dataset_result = prepare_surprise_dataset(df)
        if dataset_result:
            train_set, test_set = dataset_result

    if train_set is None:
         logger.error("Trainset is not available. Cannot load or train models.")
         return None, None, None, None

    # Load or train SVD model
    if os.path.exists(config.SVD_MODEL_PATH):
        logger.info("Loading existing SVD model...")
        try:
            with open(config.SVD_MODEL_PATH, 'rb') as f:
                svd_model = pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading SVD model: {e}. Retraining...")
            svd_model = None
    if svd_model is None:
        logger.info("Training new SVD model...")
        try:
            svd_model = SVD(**config.BEST_SVD_PARAMS)
            svd_model.fit(train_set)
            with open(config.SVD_MODEL_PATH, 'wb') as f:
                pickle.dump(svd_model, f)
            logger.info("SVD model trained and saved.")
        except Exception as e:
            logger.error(f"Error training SVD model: {e}")
            svd_model = None # Ensure it's None on failure

    # Load or train KNN model
    if os.path.exists(config.KNN_MODEL_PATH):
        logger.info("Loading existing KNN model...")
        try:
            with open(config.KNN_MODEL_PATH, 'rb') as f:
                knn_model = pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading KNN model: {e}. Retraining...")
            knn_model = None
    if knn_model is None:
        logger.info("Training new KNN model...")
        try:
            knn_model = KNNBasic(**config.BEST_KNN_PARAMS)
            knn_model.fit(train_set)
            with open(config.KNN_MODEL_PATH, 'wb') as f:
                pickle.dump(knn_model, f)
            logger.info("KNN model trained and saved.")
        except Exception as e:
            logger.error(f"Error training KNN model: {e}")
            knn_model = None # Ensure it's None on failure

    logger.info("Models loaded/trained.")
    return svd_model, knn_model, train_set, test_set


def get_knn_score(knn_model: KNNModelType, user_id: str, item_id: str) -> float:
    """Get KNN prediction score"""
    if knn_model is None: return config.NEUTRAL_SCORE
    try:
        pred = knn_model.predict(user_id, item_id)
        if pred.details.get('was_impossible', False):
            return config.NEUTRAL_SCORE
        return pred.est
    except Exception as e:
        logger.warning(f"Could not get KNN score for user {user_id}, item {item_id}: {e}")
        return config.NEUTRAL_SCORE

def get_svd_score(svd_model: SVDModelType, user_id: str, item_id: str) -> float:
    """Get SVD prediction score"""
    if svd_model is None: return config.NEUTRAL_SCORE
    try:
        pred = svd_model.predict(user_id, item_id)
        if pred.details.get('was_impossible', False):
             return config.NEUTRAL_SCORE
        return pred.est
    except Exception as e:
        logger.warning(f"Could not get SVD score for user {user_id}, item {item_id}: {e}")
        return config.NEUTRAL_SCORE

def contextual_recommendation_score(df: pd.DataFrame, business_id: str, context_city: str, context_day_period: str, context_category: str) -> float:
    """Calculate contextual score for a specific business based on average rating within the context."""
    if df is None: return config.NEUTRAL_SCORE

    try:
        # Filter businesses by the specific business_id AND context
        df_filtered = df[
            (df['business_id'] == business_id) &
            (df['city'] == context_city) &
            (df['day_period'] == context_day_period) &
            (df['categories'].str.contains(context_category, case=False, na=False))
        ]

        if df_filtered.empty:
            # Fall back to overall average rating or neutral score
            business_overall_avg = df.loc[df['business_id'] == business_id, 'stars'].mean()
            return business_overall_avg if pd.notna(business_overall_avg) else config.NEUTRAL_SCORE

        # Calculate average rating for this specific business within this context
        contextual_avg_rating = df_filtered['stars_review'].mean()
        return contextual_avg_rating if pd.notna(contextual_avg_rating) else config.NEUTRAL_SCORE
    except Exception as e:
        logger.warning(f"Error calculating contextual score for {business_id}: {e}")
        return config.NEUTRAL_SCORE


def explain_hybrid_recommendation(
    df: pd.DataFrame, svd_model: SVDModelType, knn_model: KNNModelType,
    user_id: str, context_city: str, context_day_period: str, context_category: str,
    top_n: int = config.DEFAULT_TOP_N, w_knn: float = config.DEFAULT_W_KNN,
    w_svd: float = config.DEFAULT_W_SVD, w_context: float = config.DEFAULT_W_CONTEXT
) -> List[Dict[str, Any]]:
    """Generate explainable hybrid recommendations."""
    if df is None or svd_model is None or knn_model is None:
        logger.error("Data or models not loaded, cannot generate recommendations.")
        return []

    user_exists = user_id in df['user_id'].unique()
    if not user_exists:
        logger.warning(f"User {user_id} not found in the dataset. Recommendations might be less accurate.")

    # Normalize weights
    w_total = w_knn + w_svd + w_context
    if w_total == 0:
        w_knn, w_svd, w_context = 1/3, 1/3, 1/3
    else:
        w_knn /= w_total
        w_svd /= w_total
        w_context /= w_total

    # Get candidate items and filter out seen items
    candidate_items = df[df['city'] == context_city]['business_id'].unique()
    if len(candidate_items) == 0:
        logger.warning(f"No businesses found for city {context_city}. Falling back to all businesses.")
        candidate_items = df['business_id'].unique()

    rated_items = set(df[df['user_id'] == user_id]['business_id'].unique())
    unseen_items = [iid for iid in candidate_items if iid not in rated_items]

    logger.info(f"Generating recommendations for user {user_id} from {len(unseen_items)} unseen items in {context_city}.")

    explanations = []
    items_to_score = unseen_items[:config.MAX_ITEMS_TO_SCORE]

    # Pre-fetch business info to avoid repeated lookups inside the loop
    business_info_map = df.loc[df['business_id'].isin(items_to_score),
                               ['business_id', 'name', 'address', 'categories', 'stars']] \
                          .drop_duplicates(subset=['business_id']) \
                          .set_index('business_id') \
                          .to_dict('index')

    for iid in items_to_score:
        if iid not in business_info_map:
            logger.warning(f"Business info missing for pre-fetched item {iid}")
            continue # Skip if info wasn't fetched correctly

        try:
            svd_est = get_svd_score(svd_model, user_id, iid)
            knn_est = get_knn_score(knn_model, user_id, iid)
            business_context_score = contextual_recommendation_score(
                df, iid, context_city, context_day_period, context_category
            )

            final_score = (w_knn * knn_est + w_svd * svd_est + w_context * business_context_score)

            business = business_info_map[iid]

            explanations.append({
                'business_id': iid,
                'name': business.get('name'),
                'address': business.get('address'),
                'categories': business.get('categories'),
                'overall_stars': business.get('stars'),
                'score_svd': round(svd_est, 3),
                'score_knn': round(knn_est, 3),
                'score_contextual': round(business_context_score, 3),
                'final_score': round(final_score, 4),
                'explanation': {
                    'SVD': f"Rating predicted by SVD: {round(svd_est, 2)}",
                    'KNN': f"Rating predicted by KNN: {round(knn_est, 2)}",
                    'Contextual': f"Avg rating in context: {round(business_context_score, 2)}",
                    'weights': {'w_svd': round(w_svd, 2), 'w_knn': round(w_knn, 2), 'w_context': round(w_context, 2)}
                }
            })
        except Exception as e:
            logger.error(f"Error processing item {iid} for user {user_id}: {str(e)}")
            continue

    explanations_sorted = sorted(explanations, key=lambda x: x['final_score'], reverse=True)
    logger.info(f"Generated {len(explanations_sorted)} potential recommendations, returning top {top_n}.")
    return explanations_sorted[:top_n]


def hybrid_recommendation(
    df: pd.DataFrame, svd_model: SVDModelType, knn_model: KNNModelType,
    user_id: str, context_city: str, context_day_period: str, context_category: str,
    top_n: int = config.DEFAULT_TOP_N
) -> List[Dict[str, Any]]:
    """Faster hybrid recommendation without detailed explanations."""
    if df is None or svd_model is None or knn_model is None:
        logger.error("Data or models not loaded, cannot generate quick recommendations.")
        return []

    # Get candidate items and filter out seen items
    candidate_items = df[df['city'] == context_city]['business_id'].unique()
    rated_items = set(df[df['user_id'] == user_id]['business_id'].unique())
    unseen_items = [iid for iid in candidate_items if iid not in rated_items]

    if not unseen_items:
        logger.warning(f"No unseen businesses found for user {user_id} in {context_city}")
        return []

    items_to_score = unseen_items[:config.MAX_ITEMS_TO_SCORE_QUICK]
    logger.info(f"Generating quick recommendations for {user_id} from {len(items_to_score)} candidates.")

    # Simplified Scoring (Equal Weights) - Adjust if needed
    w_knn, w_svd, w_context = 1/3, 1/3, 1/3

    # Pre-fetch business info
    business_info_map = df.loc[df['business_id'].isin(items_to_score),
                               ['business_id', 'name', 'address', 'categories', 'stars']] \
                          .drop_duplicates(subset=['business_id']) \
                          .set_index('business_id') \
                          .to_dict('index')

    def compute_scores(business_id):
        if business_id not in business_info_map: return None
        try:
            context_score = contextual_recommendation_score(
                df, business_id, context_city, context_day_period, context_category
            )
            knn_score = get_knn_score(knn_model, user_id, business_id)
            svd_score = get_svd_score(svd_model, user_id, business_id)
            final_score = (w_knn * knn_score + w_svd * svd_score + w_context * context_score)

            info = business_info_map[business_id]
            info['business_id'] = business_id
            info['final_score'] = round(final_score, 4)
            # Optional: Add individual scores
            info['score_knn'] = round(knn_score, 3)
            info['score_svd'] = round(svd_score, 3)
            info['score_context'] = round(context_score, 3)
            return info
        except Exception as e:
             logger.warning(f"Error computing score for quick rec {business_id}: {e}")
             return None

    # Parallel score computation
    results = []
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        future_results = executor.map(compute_scores, [iid for iid in items_to_score if iid in business_info_map])
        results = [result for result in future_results if result is not None]

    results_sorted = sorted(results, key=lambda x: x['final_score'], reverse=True)
    return results_sorted[:top_n]

def get_available_contexts_from_df(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Extracts available contexts (cities, periods, categories) from the DataFrame."""
    if df is None:
        return {"cities": [], "day_periods": [], "categories": []}

    try:
        cities = sorted(df['city'].dropna().unique().tolist())
        day_periods = ['morning', 'afternoon', 'evening', 'night'] # Fixed list

        categories = set()
        valid_categories = df['categories'].dropna().astype(str)
        for cat_list in valid_categories.unique():
             split_cats = [cat.strip() for cat in cat_list.split(',') if cat.strip()]
             categories.update(split_cats)

        return {
            "cities": cities,
            "day_periods": day_periods,
            "categories": sorted(list(categories))
        }
    except Exception as e:
        logger.error(f"Error extracting contexts from DataFrame: {e}")
        return {"cities": [], "day_periods": [], "categories": []}