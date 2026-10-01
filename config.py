import os


class Config:

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "smartshop-ai-development-key"
    )

    SQLALCHEMY_DATABASE_URI = "sqlite:///smartshop.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
