from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/urban"
    data_dir: Path = Path("./var/data")
    max_upload_mb: int = 250
    max_uncompressed_mb: int = 1000
    allowed_extensions: tuple[str, ...] = (
        ".csv",
        ".parquet",
        ".geojson",
        ".json",
        ".gpkg",
        ".shp",
        ".shx",
        ".dbf",
        ".prj",
        ".cpg",
        ".xlsx",
    )


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
