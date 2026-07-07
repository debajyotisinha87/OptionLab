"""
Application Configuration
Loads all environment variables from the .env file.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# Project Root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env
load_dotenv(PROJECT_ROOT / ".env")

# Dhan Credentials
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Data Folder
DATA_DIR = PROJECT_ROOT / "data"

# Database Folder
DATABASE_DIR = PROJECT_ROOT / "database"

# Log Folder
LOG_DIR = PROJECT_ROOT / "logs"

# Create directories automatically
DATA_DIR.mkdir(exist_ok=True)
DATABASE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)