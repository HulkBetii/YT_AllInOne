try:
    # Pydantic v2
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover
    # Fallback for v1 environments
    from pydantic import BaseSettings  # type: ignore


class Settings(BaseSettings):
    download_dir: str = "downloads"


settings = Settings()


def get_default_download_dir() -> str:
    import os
    home = os.path.expanduser("~")
    candidate = os.path.join(home, "Downloads")
    return candidate if os.path.isdir(candidate) or not os.path.exists(candidate) else settings.download_dir

