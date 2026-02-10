import os
import yaml
from dotenv import load_dotenv

load_dotenv()

def load_config():
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    secrets = {
        "INDIGO_USER_KEY": os.getenv("INDIGO_USER_KEY"),
        "INDIGO_AUTH_TOKEN": os.getenv("INDIGO_AUTH_TOKEN"),
    }

    missing = [k for k, v in secrets.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required Indigo environment variables: {missing}"
        )

    return config, secrets
