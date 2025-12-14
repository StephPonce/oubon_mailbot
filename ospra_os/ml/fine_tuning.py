"""
Fine-Tuning Pipeline - GROK RECOMMENDATION #15

Fast, memory-efficient fine-tuning of Llama models using Unsloth.

Capabilities:
- Fine-tune Llama 3.1 8B/70B on custom datasets
- 2x faster training than standard methods
- 60% less memory usage
- LoRA for efficient parameter updates
- Export to GGUF for Ollama deployment
- Upload to Together.ai for cheap API access

Workflow:
1. Load base Llama model with Unsloth
2. Prepare training data (JSONL -> Hugging Face dataset)
3. Configure LoRA (rank, alpha, dropout)
4. Train with optimized settings
5. Save adapter weights
6. Merge and quantize to GGUF
7. Deploy to Ollama
8. (Optional) Upload to Together.ai

Requirements:
- unsloth (pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git")
- transformers, datasets, peft, trl
- llama.cpp (for GGUF conversion)
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FineTuningConfig:
    """Fine-tuning configuration"""

    # Model settings
    base_model: str = "unsloth/Meta-Llama-3.1-8B-Instruct"  # Unsloth optimized
    max_seq_length: int = 2048

    # LoRA settings
    lora_r: int = 16  # Rank (higher = more capacity, slower)
    lora_alpha: int = 16  # Scaling factor
    lora_dropout: float = 0.0  # Dropout (usually 0 for stability)
    target_modules: List[str] = None  # Auto-detect

    # Training settings
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 4  # Effective batch size = 2 * 4 = 8
    learning_rate: float = 2e-4
    warmup_steps: int = 5
    max_steps: int = -1  # -1 means train for full epochs

    # Optimization
    fp16: bool = False  # Use bf16 instead on modern GPUs
    bf16: bool = True
    optim: str = "adamw_8bit"  # Memory-efficient optimizer
    weight_decay: float = 0.01

    # Logging
    logging_steps: int = 10
    save_steps: int = 100

    # Output
    output_dir: str = "models/fine-tuned"

    def __post_init__(self):
        """Set default target modules if not specified"""
        if self.target_modules is None:
            self.target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                                    "gate_proj", "up_proj", "down_proj"]


class FineTuningPipeline:
    """
    Fine-tuning pipeline using Unsloth for speed and efficiency.

    Example:
        pipeline = FineTuningPipeline(config)

        # Train on custom data
        model, tokenizer = pipeline.fine_tune(
            dataset_path="training_data/product_scoring_20251210.jsonl",
            task_type="product_scoring"
        )

        # Export for Ollama
        pipeline.export_to_gguf(
            model=model,
            tokenizer=tokenizer,
            output_path="models/ospra-product-scorer-8b.gguf"
        )

        # Deploy to Ollama
        pipeline.deploy_to_ollama(
            gguf_path="models/ospra-product-scorer-8b.gguf",
            model_name="ospra-product-scorer"
        )
    """

    def __init__(self, config: Optional[FineTuningConfig] = None):
        self.config = config or FineTuningConfig()
        logger.info(f"FineTuningPipeline initialized with base model: {self.config.base_model}")

    def load_dataset(self, dataset_path: str) -> Any:
        """
        Load training dataset from JSONL file.

        Expected format (OpenAI chat format):
        {"messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]}

        Returns Hugging Face dataset.
        """

        try:
            from datasets import Dataset
            import pandas as pd

            logger.info(f"Loading dataset from {dataset_path}")

            # Read JSONL
            data = []
            with open(dataset_path, 'r') as f:
                for line in f:
                    data.append(json.loads(line))

            # Convert to Hugging Face format
            # For chat models, we need to format as conversations
            formatted_data = []
            for item in data:
                # Extract messages
                messages = item.get("messages", [])

                # Combine into single text with special tokens
                text = ""
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]

                    if role == "system":
                        text += f"<|system|>\n{content}\n"
                    elif role == "user":
                        text += f"<|user|>\n{content}\n"
                    elif role == "assistant":
                        text += f"<|assistant|>\n{content}\n"

                formatted_data.append({"text": text})

            # Create dataset
            df = pd.DataFrame(formatted_data)
            dataset = Dataset.from_pandas(df)

            logger.info(f"Loaded {len(dataset)} training examples")
            return dataset

        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            raise

    def fine_tune(
        self,
        dataset_path: str,
        task_type: str,
        validation_split: float = 0.1
    ) -> tuple:
        """
        Fine-tune Llama model on custom dataset.

        Args:
            dataset_path: Path to JSONL training data
            task_type: Task type (for naming)
            validation_split: Fraction of data for validation

        Returns:
            (model, tokenizer) tuple
        """

        logger.info(f"Starting fine-tuning for task: {task_type}")

        try:
            # Import here to avoid requiring unsloth if not fine-tuning
            from unsloth import FastLanguageModel
            from trl import SFTTrainer
            from transformers import TrainingArguments

            # 1. Load base model with Unsloth optimizations
            logger.info(f"Loading base model: {self.config.base_model}")

            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=self.config.base_model,
                max_seq_length=self.config.max_seq_length,
                dtype=None,  # Auto-detect
                load_in_4bit=True,  # Use 4-bit quantization for memory efficiency
            )

            # 2. Add LoRA adapters
            logger.info("Adding LoRA adapters")

            model = FastLanguageModel.get_peft_model(
                model,
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=self.config.target_modules,
                bias="none",
                use_gradient_checkpointing="unsloth",  # Unsloth's optimized checkpointing
                random_state=42,
            )

            # 3. Load dataset
            dataset = self.load_dataset(dataset_path)

            # Split into train/val
            if validation_split > 0:
                split_dataset = dataset.train_test_split(test_size=validation_split, seed=42)
                train_dataset = split_dataset["train"]
                eval_dataset = split_dataset["test"]
            else:
                train_dataset = dataset
                eval_dataset = None

            # 4. Configure training
            output_dir = Path(self.config.output_dir) / task_type
            output_dir.mkdir(parents=True, exist_ok=True)

            training_args = TrainingArguments(
                output_dir=str(output_dir),
                num_train_epochs=self.config.num_train_epochs,
                per_device_train_batch_size=self.config.per_device_train_batch_size,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                warmup_steps=self.config.warmup_steps,
                max_steps=self.config.max_steps,
                learning_rate=self.config.learning_rate,
                fp16=self.config.fp16,
                bf16=self.config.bf16,
                logging_steps=self.config.logging_steps,
                save_steps=self.config.save_steps,
                optim=self.config.optim,
                weight_decay=self.config.weight_decay,
                lr_scheduler_type="linear",
                seed=42,
                report_to="none",  # Disable wandb/tensorboard
            )

            # 5. Create trainer
            trainer = SFTTrainer(
                model=model,
                tokenizer=tokenizer,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                dataset_text_field="text",
                max_seq_length=self.config.max_seq_length,
                args=training_args,
            )

            # 6. Train!
            logger.info("Starting training...")
            trainer.train()

            # 7. Save model
            logger.info(f"Saving fine-tuned model to {output_dir}")
            model.save_pretrained(str(output_dir))
            tokenizer.save_pretrained(str(output_dir))

            logger.info("Fine-tuning complete!")
            return model, tokenizer

        except ImportError as e:
            logger.error(
                f"Missing dependencies for fine-tuning: {e}\n"
                "Install with: pip install unsloth transformers datasets peft trl"
            )
            raise
        except Exception as e:
            logger.error(f"Error during fine-tuning: {e}")
            raise

    def export_to_gguf(
        self,
        model: Any,
        tokenizer: Any,
        output_path: str,
        quantization: str = "q4_k_m"
    ) -> Path:
        """
        Export fine-tuned model to GGUF format for Ollama.

        Args:
            model: Fine-tuned model
            tokenizer: Tokenizer
            output_path: Output file path (.gguf)
            quantization: Quantization method (q4_k_m, q5_k_m, q8_0)

        Returns:
            Path to GGUF file
        """

        try:
            from unsloth import FastLanguageModel

            logger.info(f"Exporting to GGUF: {output_path}")

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Unsloth provides easy GGUF export
            model.save_pretrained_gguf(
                str(output_path.parent),
                tokenizer,
                quantization_method=quantization
            )

            # Unsloth creates multiple quantization files
            # Find the one matching our requested quantization
            gguf_files = list(output_path.parent.glob(f"*{quantization}*.gguf"))

            if gguf_files:
                actual_path = gguf_files[0]
                # Rename to our desired output path
                actual_path.rename(output_path)
                logger.info(f"GGUF export complete: {output_path}")
                return output_path
            else:
                raise FileNotFoundError(f"GGUF file not found after export")

        except Exception as e:
            logger.error(f"Error exporting to GGUF: {e}")
            raise

    def deploy_to_ollama(
        self,
        gguf_path: str,
        model_name: str,
        system_prompt: Optional[str] = None
    ) -> bool:
        """
        Deploy GGUF model to local Ollama.

        Creates a Modelfile and registers the model with Ollama.

        Args:
            gguf_path: Path to GGUF file
            model_name: Name for the model in Ollama (e.g., "ospra-product-scorer")
            system_prompt: Optional system prompt to bake into model

        Returns:
            True if successful
        """

        try:
            import subprocess
            import tempfile

            logger.info(f"Deploying {gguf_path} to Ollama as '{model_name}'")

            # Create Modelfile
            modelfile_content = f"""FROM {gguf_path}

# Model parameters
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
"""

            if system_prompt:
                modelfile_content += f'\nSYSTEM """{system_prompt}"""\n'

            # Write Modelfile to temp location
            with tempfile.NamedTemporaryFile(mode='w', suffix='_Modelfile', delete=False) as f:
                f.write(modelfile_content)
                modelfile_path = f.name

            try:
                # Create model in Ollama
                result = subprocess.run(
                    ["ollama", "create", model_name, "-f", modelfile_path],
                    capture_output=True,
                    text=True,
                    check=True
                )

                logger.info(f"Model '{model_name}' deployed to Ollama")
                logger.info(f"Test with: ollama run {model_name}")
                return True

            finally:
                # Clean up temp file
                Path(modelfile_path).unlink(missing_ok=True)

        except subprocess.CalledProcessError as e:
            logger.error(f"Ollama deployment failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error deploying to Ollama: {e}")
            return False

    def upload_to_together(
        self,
        model_path: str,
        model_name: str,
        together_api_key: Optional[str] = None
    ) -> bool:
        """
        Upload fine-tuned model to Together.ai for cheap API access.

        Args:
            model_path: Path to model directory (with adapter weights)
            model_name: Name for the model on Together.ai
            together_api_key: Together.ai API key (or use env var)

        Returns:
            True if successful

        Note: This is a placeholder - Together.ai's model upload API
              is in private beta. For now, use their web interface to
              upload models.
        """

        api_key = together_api_key or os.getenv("TOGETHER_API_KEY")

        if not api_key:
            logger.error("TOGETHER_API_KEY not set")
            return False

        logger.warning(
            "Together.ai model upload via API is in private beta. "
            "Upload manually at: https://api.together.ai/models/upload"
        )

        logger.info(f"Model ready for upload: {model_path}")
        logger.info(f"Suggested name: {model_name}")

        return False  # Not implemented yet

    def test_model(
        self,
        model: Any,
        tokenizer: Any,
        test_prompts: List[str]
    ) -> List[str]:
        """
        Test fine-tuned model with sample prompts.

        Args:
            model: Fine-tuned model
            tokenizer: Tokenizer
            test_prompts: List of test prompts

        Returns:
            List of generated responses
        """

        try:
            from unsloth import FastLanguageModel

            logger.info(f"Testing model with {len(test_prompts)} prompts")

            # Enable inference mode
            FastLanguageModel.for_inference(model)

            responses = []

            for prompt in test_prompts:
                # Tokenize
                inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

                # Generate
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=256,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True
                )

                # Decode
                response = tokenizer.decode(outputs[0], skip_special_tokens=True)

                # Extract just the assistant response (remove prompt)
                response = response[len(prompt):].strip()

                responses.append(response)

                logger.info(f"Prompt: {prompt[:50]}...")
                logger.info(f"Response: {response[:100]}...")

            return responses

        except Exception as e:
            logger.error(f"Error testing model: {e}")
            return []

    def get_training_status(self, task_type: str) -> Dict[str, Any]:
        """
        Get status of fine-tuning job.

        Args:
            task_type: Task type to check

        Returns:
            Status dict with checkpoints, metrics, etc.
        """

        output_dir = Path(self.config.output_dir) / task_type

        if not output_dir.exists():
            return {
                "status": "not_started",
                "task_type": task_type,
                "output_dir": str(output_dir)
            }

        # Check for checkpoints
        checkpoints = list(output_dir.glob("checkpoint-*"))

        # Check for final model
        has_final_model = (output_dir / "adapter_model.safetensors").exists()

        status = {
            "status": "completed" if has_final_model else "in_progress",
            "task_type": task_type,
            "output_dir": str(output_dir),
            "num_checkpoints": len(checkpoints),
            "has_final_model": has_final_model
        }

        return status
