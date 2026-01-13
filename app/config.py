from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GITHUB_TOKEN: str
    BITBUCKET_USERNAME: str
    BITBUCKET_TOKEN: str
    GEMINI_API_KEY: str


    class Config:
        env_file = ".env"
   
settings = Settings()

print("GITHUB_TOKEN loaded:", bool(settings.GITHUB_TOKEN))
print("BITBUCKET_USERNAME loaded:", bool(settings.BITBUCKET_USERNAME))
print("BITBUCKET_TOKEN loaded:", bool(settings.BITBUCKET_TOKEN))

