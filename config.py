from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Config(BaseSettings):
    BOT_TOKEN: SecretStr

    class Config:
        env_file = ".env"

config = Config()