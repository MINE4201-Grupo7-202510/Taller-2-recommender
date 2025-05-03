import os
import pickle
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine
from typing import Optional, Tuple, List, Dict, Any

# Import modules
import config
import models
import database
import recommender
import utils

# --- Global State ---
# These variables will be initialized during startup
app_state: Dict[str, Any] = {
    "engine": None,
    "df": None,
    "svd_model": None,
    "knn_model": None,
    "train_set": None,
    "test_set": None,
    "data_loaded": False,
    "models_loaded": False
}

# Get logger instance
logger = utils.get_logger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Hybrid Restaurant Recommendation System",
    description="API for recommending restaurants using a hybrid model approach (DB Version, Refactored)",
    version="1.2.0" # Updated version
)


# Add CORSMiddleware to the application
app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"],  # List of origins allowed
    allow_credentials=True, # Allow cookies to be included in requests
    allow_methods=["*"],    # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],    # Allow all headers
)


# --- Dependency Functions ---
# These functions provide access to the global state, ensuring components are loaded.
def get_engine() -> Engine:
    engine = app_state.get("engine")
    if engine is None:
        logger.error("Database engine not available.")
        raise HTTPException(status_code=503, detail="Service Unavailable: Database connection not established.")
    return engine

def get_dataframe() -> pd.DataFrame:
    df = app_state.get("df")
    if df is None or not app_state.get("data_loaded"):
        logger.error("DataFrame not available.")
        raise HTTPException(status_code=503, detail="Service Unavailable: Data not loaded.")
    return df

def get_models() -> Tuple[recommender.SVDModelType, recommender.KNNModelType]:
    svd_model = app_state.get("svd_model")
    knn_model = app_state.get("knn_model")
    if svd_model is None or knn_model is None or not app_state.get("models_loaded"):
        logger.error("Models not available.")
        raise HTTPException(status_code=503, detail="Service Unavailable: Models not loaded.")
    return svd_model, knn_model

# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    """Initialize database connection, load data, and models on startup"""
    logger.info("Application startup...")

    # 1. Create DB Engine
    engine = database.create_db_engine()
    if engine is None:
        logger.error("Database connection failed. API cannot start properly.")
        # Allow startup but endpoints requiring DB/data will fail
        return
    app_state["engine"] = engine

    # 2. Load Data
    df = database.load_data(engine)
    if df is None:
        logger.error("Failed to load data. API functionality will be limited.")
        return # Stop if data loading fails
    app_state["df"] = df
    app_state["data_loaded"] = True

    # 3. Load or Train Models
    svd_model, knn_model, train_set, test_set = recommender.load_or_train_models(df)
    if svd_model is None or knn_model is None:
        logger.error("Failed to load or train models. API functionality will be limited.")
        # Models might be partially loaded, update state accordingly
        app_state["svd_model"] = svd_model
        app_state["knn_model"] = knn_model
        app_state["train_set"] = train_set
        app_state["test_set"] = test_set
        # Keep models_loaded as False if any model failed
    else:
        app_state["svd_model"] = svd_model
        app_state["knn_model"] = knn_model
        app_state["train_set"] = train_set
        app_state["test_set"] = test_set
        app_state["models_loaded"] = True
        logger.info("Data and models loaded successfully.")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    logger.info("Application shutdown...")
    engine = app_state.get("engine")
    if engine:
        engine.dispose()
        logger.info("Database engine disposed.")
    # Clear state
    app_state.clear()

# --- API Endpoints ---
@app.get("/", response_model=models.HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    status = "online"
    message = "Hybrid Restaurant Recommendation System API is running"
    if not app_state.get("data_loaded") or not app_state.get("models_loaded"):
        status = "degraded"
        issues = []
        if not app_state.get("engine"): issues.append("DB connection failed")
        if not app_state.get("data_loaded"): issues.append("Data not loaded")
        if not app_state.get("models_loaded"): issues.append("Models not loaded")
        message += f" (Warning: {', '.join(issues)})"
    return {"status": status, "message": message}

@app.post("/recommendations", response_model=models.RecommendationResponse, tags=["Recommendations"])
async def get_recommendations(
    request: models.RecommendationRequest,
    df: pd.DataFrame = Depends(get_dataframe),
    models_tuple: Tuple[recommender.SVDModelType, recommender.KNNModelType] = Depends(get_models)
):
    """Get hybrid recommendations with detailed explanations"""
    svd_model, knn_model = models_tuple
    try:
        recommendations_list = recommender.explain_hybrid_recommendation(
            df=df, svd_model=svd_model, knn_model=knn_model,
            user_id=request.user_id,
            context_city=request.context_city,
            context_day_period=request.context_day_period,
            context_category=request.context_category,
            top_n=request.top_n,
            w_knn=request.w_knn,
            w_svd=request.w_svd,
            w_context=request.w_context
        )

        if not recommendations_list:
             logger.info(f"No recommendations found for user {request.user_id} with the given context.")
             # Return empty list in response body

        response = models.RecommendationResponse(
            recommendations=recommendations_list,
            model_info={
                "svd_params": config.BEST_SVD_PARAMS,
                "knn_params": config.BEST_KNN_PARAMS,
                "request_weights": {
                    "w_knn": request.w_knn,
                    "w_svd": request.w_svd,
                    "w_context": request.w_context
                },
                "data_source": "PostgreSQL Database"
            }
        )
        return response
    except Exception as e:
        logger.error(f"Error generating recommendations for request {request}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error generating recommendations.")

@app.get("/recommendations/quick", response_model=models.QuickRecommendationResponse, tags=["Recommendations"])
async def get_quick_recommendations(
    user_id: str = Query(..., description="User ID"),
    city: str = Query(..., description="Context city"),
    day_period: str = Query(..., description="Day period (morning, afternoon, evening, night)"),
    category: str = Query(..., description="Business category"),
    top_n: int = Query(config.DEFAULT_TOP_N, ge=1, le=50, description="Number of recommendations"),
    df: pd.DataFrame = Depends(get_dataframe),
    models_tuple: Tuple[recommender.SVDModelType, recommender.KNNModelType] = Depends(get_models)
):
    """Get quick hybrid recommendations without detailed explanations"""
    svd_model, knn_model = models_tuple
    try:
        recommendations_list = recommender.hybrid_recommendation(
            df=df, svd_model=svd_model, knn_model=knn_model,
            user_id=user_id,
            context_city=city,
            context_day_period=day_period,
            context_category=category,
            top_n=top_n
        )

        if not recommendations_list:
             logger.info(f"No quick recommendations found for user {user_id} with the given context.")

        # Validate output against Pydantic model before returning
        validated_recommendations = [models.QuickRecommendationItem(**item) for item in recommendations_list]

        return {"recommendations": validated_recommendations}
    except Exception as e:
        logger.error(f"Error generating quick recommendations for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error generating quick recommendations.")

@app.get("/available-contexts", response_model=models.Contexts, tags=["Context"])
async def get_available_contexts(df: pd.DataFrame = Depends(get_dataframe)):
    """Get all available contexts for recommendations"""
    try:
        contexts = recommender.get_available_contexts_from_df(df)
        return contexts
    except Exception as e:
        logger.error(f"Error getting available contexts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error retrieving contexts.")

@app.get("/user/{user_id}/history", response_model=models.UserProfile, tags=["User"])
async def get_user_history(
    user_id: str,
    engine: Engine = Depends(get_engine),
    # Make DataFrame dependency optional here, as we might fetch from DB if df is missing
    df: Optional[pd.DataFrame] = Depends(lambda: app_state.get("df")) # Allow None
):
    """Get user's rating history and profile"""
    try:
        user_data = database.get_user_profile_and_history(engine, df, user_id)
        if user_data is None:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")
        return user_data
    except HTTPException as he:
        raise he # Re-raise known HTTP exceptions
    except Exception as e:
        logger.error(f"Error fetching history for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching user history.")


@app.post("/models/retrain", response_model=models.RetrainResponse, tags=["Admin"])
async def retrain_models(engine: Engine = Depends(get_engine)):
    """Force data reload, dataset preparation, and model retraining"""
    logger.info("Received request to force model retraining...")

    # 1. Clear existing model/dataset artifacts from memory and state
    app_state["df"] = None
    app_state["train_set"] = None
    app_state["test_set"] = None
    app_state["svd_model"] = None
    app_state["knn_model"] = None
    app_state["data_loaded"] = False
    app_state["models_loaded"] = False

    # 2. Remove existing model files from disk
    try:
        utils.ensure_model_dir() # Ensure dir exists before trying to remove
        if os.path.exists(config.SVD_MODEL_PATH):
            os.remove(config.SVD_MODEL_PATH)
            logger.info(f"Removed existing SVD model file: {config.SVD_MODEL_PATH}")
        if os.path.exists(config.KNN_MODEL_PATH):
            os.remove(config.KNN_MODEL_PATH)
            logger.info(f"Removed existing KNN model file: {config.KNN_MODEL_PATH}")
        if os.path.exists(config.DATASET_PATH):
            os.remove(config.DATASET_PATH)
            logger.info(f"Removed existing dataset file: {config.DATASET_PATH}")
    except OSError as e:
        logger.error(f"Error removing model files: {e}")
        # Decide if this is critical - maybe proceed anyway?
        raise HTTPException(status_code=500, detail=f"Error removing existing model files: {e}")

    # 3. Reload data from DB
    df = database.load_data(engine)
    if df is None:
        raise HTTPException(status_code=500, detail="Error reloading data from database during retrain.")
    app_state["df"] = df
    app_state["data_loaded"] = True

    # 4. Prepare dataset and train models
    svd_model, knn_model, train_set, test_set = recommender.load_or_train_models(df)
    if svd_model is None or knn_model is None:
         # Update state even if partial failure
        app_state["svd_model"] = svd_model
        app_state["knn_model"] = knn_model
        app_state["train_set"] = train_set
        app_state["test_set"] = test_set
        raise HTTPException(status_code=500, detail="Error preparing dataset or retraining models.")
    else:
        app_state["svd_model"] = svd_model
        app_state["knn_model"] = knn_model
        app_state["train_set"] = train_set
        app_state["test_set"] = test_set
        app_state["models_loaded"] = True
        logger.info("Models retrained successfully.")
        return {"status": "success", "message": "Data reloaded and models retrained successfully"}


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    # Make sure DB environment variables are set before running
    print("--- Ensure Database Environment Variables Are Set ---")
    print(f"DB_USER: {config.DB_USER}")
    print(f"DB_PASSWORD: {'*' * len(config.DB_PASSWORD)}") # Hide password
    print(f"DB_HOST: {config.DB_HOST}")
    print(f"DB_PORT: {config.DB_PORT}")
    print(f"DB_NAME: {config.DB_NAME}")
    print("--- Starting FastAPI Application ---")
    # Note: The startup event will handle the initial loading.
    uvicorn.run(app, host="0.0.0.0", port=8000)
