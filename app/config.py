from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GITHUB_TOKEN: str
    GEMINI_API_KEY: str


    class Config:
        env_file = ".env"
   
settings = Settings()

print("GITHUB_TOKEN loaded:", bool(settings.GITHUB_TOKEN))
