from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    app_name: str = "household_cleaning_robot"
    
    
    model_config = SettingsConfigDict(env_file = ".env")
    
    db_host: str
    db_port: int
    db_user: str = "postgres"
    db_psw: SecretStr
    db_name: str = "eventone"
    

    secret_key: SecretStr 
    algorithm: str 
    access_token_expire_minutes: int 


settings = Settings()  