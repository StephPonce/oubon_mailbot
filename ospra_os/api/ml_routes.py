"""
ML API Routes - GROK RECOMMENDATION #15

REST API for ML operations:
- Cost tracking and reporting
- Training data collection
- Fine-tuning jobs
- Model testing
- AI generation with automatic routing

Endpoints:
- GET /api/ml/cost-report - Get cost analysis and savings
- POST /api/ml/collect-training-data - Collect training data
- POST /api/ml/fine-tune/{task_type} - Start fine-tuning job
- POST /api/ml/generate - Generate AI response with routing
- GET /api/ml/models - List available models
- GET /api/ml/training-status/{task_type} - Get fine-tuning status
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from ospra_os.database.db import get_db
from ospra_os.ml import ai_client, ModelTier
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User
from ospra_os.ml.training_data import TrainingDataCollector
from ospra_os.ml.fine_tuning import FineTuningPipeline, FineTuningConfig

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ML"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class GenerateRequest(BaseModel):
    """Request for AI generation"""
    prompt: str = Field(..., description="User prompt")
    task_type: str = Field(default="general", description="Task type for routing")
    system_prompt: Optional[str] = Field(None, description="System instructions")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int = Field(default=1024, gt=0, le=4096, description="Max tokens to generate")
    force_tier: Optional[str] = Field(None, description="Force specific tier (local/cheap/premium)")


class GenerateResponse(BaseModel):
    """Response from AI generation"""
    content: str
    model: str
    tokens: int
    cost: float
    tier: str
    provider: str


class CollectTrainingDataRequest(BaseModel):
    """Request to collect training data"""
    task_types: Optional[List[str]] = Field(None, description="Specific task types (or all)")
    min_quality: float = Field(default=0.7, ge=0, le=1, description="Minimum quality score")
    examples_per_task: int = Field(default=1000, gt=0, description="Max examples per task")


class FineTuneRequest(BaseModel):
    """Request to start fine-tuning"""
    dataset_path: str = Field(..., description="Path to training data JSONL")
    base_model: Optional[str] = Field(None, description="Base model to fine-tune")
    num_epochs: int = Field(default=3, gt=0, le=10, description="Training epochs")
    learning_rate: float = Field(default=2e-4, gt=0, description="Learning rate")
    deploy_to_ollama: bool = Field(default=True, description="Deploy to Ollama after training")


class ProductScoreRequest(BaseModel):
    """Request to score a product"""
    product_name: str
    category: str
    price: float
    competition: str
    trend_data: Optional[Dict] = None


class EmailResponseRequest(BaseModel):
    """Request to generate email response"""
    customer_email: str
    context: Optional[str] = None
    tone: str = Field(default="friendly", description="Response tone")


class AdCopyRequest(BaseModel):
    """Request to generate ad copy"""
    product_name: str
    key_features: List[str]
    target_audience: str
    platform: str = Field(default="facebook", description="Ad platform")


# ============================================================================
# COST TRACKING & REPORTING
# ============================================================================

@router.get("/cost-report")
async def get_cost_report(current_user: User = Depends(get_current_user)):
    """
    Get AI cost analysis and savings report.

    Returns detailed breakdown by tier and savings vs all-Claude approach.
    """
    try:
        report = ai_client.get_usage_report()
        return {
            "status": "success",
            "report": report,
            "message": f"Saved ${report['summary']['savings_amount']} ({report['summary']['savings_percent']}%)"
        }
    except Exception as e:
        logger.error(f"Error getting cost report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/reset-stats")
async def reset_cost_stats(current_user: User = Depends(get_current_user)):
    """
    Reset usage statistics.

    Useful for monthly cost tracking.
    """
    try:
        ai_client.reset_stats()
        return {
            "status": "success",
            "message": "Usage statistics reset"
        }
    except Exception as e:
        logger.error(f"Error resetting stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# AI GENERATION
# ============================================================================

@router.post("/generate", response_model=GenerateResponse)
async def generate_ai_response(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate AI response with automatic model routing.

    Routes to optimal model based on task complexity and cost.
    """
    try:
        # Parse force_tier if provided
        force_tier = None
        if request.force_tier:
            force_tier = ModelTier(request.force_tier)

        # Generate
        response = ai_client.generate(
            prompt=request.prompt,
            task_type=request.task_type,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            force_tier=force_tier
        )

        return GenerateResponse(
            content=response.content,
            model=response.model,
            tokens=response.tokens,
            cost=response.cost,
            tier=response.tier,
            provider=response.provider
        )

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# HELPER ENDPOINTS
# ============================================================================

@router.post("/score-product")
async def score_product(
    request: ProductScoreRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Score a product's e-commerce potential.

    Returns score (1-100), reasoning, and recommendations.
    """
    try:
        result = ai_client.score_product(
            product_name=request.product_name,
            category=request.category,
            price=request.price,
            competition=request.competition,
            trend_data=request.trend_data
        )
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Error scoring product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/generate-email-response")
async def generate_email_response(
    request: EmailResponseRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate email response to customer inquiry.

    Returns drafted email response.
    """
    try:
        response = ai_client.generate_email_response(
            customer_email=request.customer_email,
            context=request.context,
            tone=request.tone
        )
        return {
            "status": "success",
            "response": response
        }
    except Exception as e:
        logger.error(f"Error generating email response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/generate-ad-copy")
async def generate_ad_copy(
    request: AdCopyRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate ad copy for a product.

    Returns headline, body, and CTA.
    """
    try:
        result = ai_client.generate_ad_copy(
            product_name=request.product_name,
            key_features=request.key_features,
            target_audience=request.target_audience,
            platform=request.platform
        )
        return {
            "status": "success",
            "ad_copy": result
        }
    except Exception as e:
        logger.error(f"Error generating ad copy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# TRAINING DATA COLLECTION
# ============================================================================

@router.post("/collect-training-data")
async def collect_training_data(
    request: CollectTrainingDataRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Collect training data from operational database.

    Runs in background. Mines high-quality examples for fine-tuning.
    """
    try:
        def collect_data():
            """Background task to collect training data"""
            try:
                collector = TrainingDataCollector(db)

                # Collect data
                all_examples = collector.collect_all(
                    min_quality=request.min_quality,
                    examples_per_task=request.examples_per_task
                )

                # Export to JSONL
                exported_files = collector.export_all(all_examples)

                # Get statistics
                stats = collector.get_statistics(all_examples)

                logger.info(f"Training data collection complete: {stats}")

            except Exception as e:
                logger.error(f"Error in background training data collection: {e}")

        # Start background task
        background_tasks.add_task(collect_data)

        return {
            "status": "started",
            "message": "Training data collection started in background",
            "config": {
                "min_quality": request.min_quality,
                "examples_per_task": request.examples_per_task
            }
        }

    except Exception as e:
        logger.error(f"Error starting training data collection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# FINE-TUNING
# ============================================================================

@router.post("/fine-tune/{task_type}")
async def start_fine_tuning(
    task_type: str,
    request: FineTuneRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Start fine-tuning job for a task type.

    Runs in background. Trains Llama model on collected data.
    """
    try:
        def fine_tune_model():
            """Background task to fine-tune model"""
            try:
                # Create config
                config = FineTuningConfig(
                    base_model=request.base_model or "unsloth/Meta-Llama-3.1-8B-Instruct",
                    num_train_epochs=request.num_epochs,
                    learning_rate=request.learning_rate
                )

                # Create pipeline
                pipeline = FineTuningPipeline(config)

                # Fine-tune
                model, tokenizer = pipeline.fine_tune(
                    dataset_path=request.dataset_path,
                    task_type=task_type
                )

                logger.info(f"Fine-tuning complete for {task_type}")

                # Deploy to Ollama if requested
                if request.deploy_to_ollama:
                    gguf_path = f"models/ospra-{task_type}-8b.gguf"
                    pipeline.export_to_gguf(model, tokenizer, gguf_path)
                    pipeline.deploy_to_ollama(
                        gguf_path=gguf_path,
                        model_name=f"ospra-{task_type}"
                    )
                    logger.info(f"Model deployed to Ollama as 'ospra-{task_type}'")

            except Exception as e:
                logger.error(f"Error in background fine-tuning: {e}")

        # Start background task
        background_tasks.add_task(fine_tune_model)

        return {
            "status": "started",
            "message": f"Fine-tuning started for {task_type}",
            "task_type": task_type,
            "config": {
                "dataset": request.dataset_path,
                "base_model": request.base_model or "unsloth/Meta-Llama-3.1-8B-Instruct",
                "epochs": request.num_epochs,
                "deploy_to_ollama": request.deploy_to_ollama
            }
        }

    except Exception as e:
        logger.error(f"Error starting fine-tuning: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/training-status/{task_type}")
async def get_training_status(
    task_type: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get status of fine-tuning job.

    Returns progress, checkpoints, and completion status.
    """
    try:
        pipeline = FineTuningPipeline()
        status_info = pipeline.get_training_status(task_type)

        return {
            "status": "success",
            "training": status_info
        }

    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# MODEL MANAGEMENT
# ============================================================================

@router.get("/models")
async def list_available_models(current_user: User = Depends(get_current_user)):
    """
    List all available AI models.

    Includes cost, tier, and availability.
    """
    try:
        from ospra_os.ml.model_router import MODELS

        models_list = []

        for model_id, config in MODELS.items():
            models_list.append({
                "id": model_id,
                "name": config.name,
                "tier": config.tier.value,
                "cost_per_1k_tokens": config.cost_per_1k_tokens,
                "max_tokens": config.max_tokens,
                "supports_functions": config.supports_functions,
                "supports_vision": config.supports_vision
            })

        # Check provider availability
        providers_status = {
            "ollama": ai_client.providers["ollama"].is_available(),
            "groq": ai_client.providers["groq"].is_available(),
            "together": ai_client.providers["together"].is_available(),
            "claude": ai_client.providers["claude"].is_available(),
        }

        return {
            "status": "success",
            "models": models_list,
            "providers": providers_status,
            "total_models": len(models_list)
        }

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/task-complexity")
async def get_task_complexity_mapping(current_user: User = Depends(get_current_user)):
    """
    Get mapping of task types to complexity levels.

    Shows how tasks are routed to different model tiers.
    """
    try:
        from ospra_os.ml.model_router import TASK_COMPLEXITY

        mapping = {
            task: complexity.value
            for task, complexity in TASK_COMPLEXITY.items()
        }

        return {
            "status": "success",
            "mapping": mapping,
            "total_tasks": len(mapping)
        }

    except Exception as e:
        logger.error(f"Error getting task complexity mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def ml_health():
    """
    Health check for ML service.

    Tests AI client initialization and provider availability.
    """
    return {
        "status": "healthy",
        "service": "ml",
        "features": {
            "cost_optimization": True,
            "model_routing": True,
            "training_data_collection": True,
            "fine_tuning": True,
            "multi_provider": True
        },
        "providers": {
            "ollama": ai_client.providers["ollama"].is_available(),
            "groq": ai_client.providers["groq"].is_available(),
            "together": ai_client.providers["together"].is_available(),
            "claude": ai_client.providers["claude"].is_available(),
        }
    }
