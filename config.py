import os

# Fallback .env parser to avoid extra dependency
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# Grid settings
GRID_SIZE = 32
VISION_RADIUS = 3  # Chebyshev, yields a 7x7 visible window

# Biome configuration
BARRENS_PCT = 0.60
CHOKEPOINTS_PCT = 0.15
NUM_VAULTS = 4  # 3 to 5 fixed vault locations

# Economy parameters (charge costs/rewards)
STARTING_CHARGE = 100.0
METABOLIC_TAX = 1.0
MOVE_COST = 0.5  # Additional charge cost on top of metabolic tax
LLM_THINK_TAX_FLAT = 2.0  # Cognitive tax for LLM call
LLM_THINK_TAX_TOKEN_SCALE = 0.01  # Cognitive tax per output token
FORAGE_YIELD_MIN = 15.0
FORAGE_YIELD_MAX = 25.0
VAULT_ATTEMPT_COST = 10.0  # Flat cost to attempt a vault
VAULT_SOLVE_MIN = 80.0
VAULT_SOLVE_MAX = 120.0
WRITE_SIGN_COST = 3.0  # Cost to write a sign
NODE_REGEN_TICKS = 15

# LLM API configuration
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/v1/chat/completions")
DEFAULT_MODEL = os.environ.get("JUNK_WORLD_MODEL", "mistral")
LLM_TEMPERATURE = 0.2

# Logging configurations
LOG_DIR = "logs"
TICK_LOG_FILE = os.path.join(LOG_DIR, "ticks.csv")
GEN_LOG_FILE = os.path.join(LOG_DIR, "generations.csv")
LLM_LOG_FILE = os.path.join(LOG_DIR, "llm_calls.jsonl")

# Dynamic degradation calculators
def get_episodic_memory_limit(generation: int) -> int:
    """Returns K, the number of conversation turns to retain."""
    return max(4, 20 - 2 * generation)

def get_max_tokens_limit(generation: int) -> int:
    """Returns the reasoning token limit for LLM generation."""
    return max(60, 300 - 20 * generation)
