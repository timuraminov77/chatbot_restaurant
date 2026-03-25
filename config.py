import os
from dotenv import load_dotenv
from pathlib import Path


load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", 3306))
DB_USER     = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME", "restaurant")

BASE_DIR = Path(__file__).parent  # всегда корень проекта, независимо от запуска
CHROMA_PATH = os.getenv("CHROMA_PATH", str(BASE_DIR / "RAG" / "chroma_db"))
INFO_MD_PATH = os.getenv("INFO_MD_PATH", "./info.md")
ADMIN_TG_ID = 7533405423