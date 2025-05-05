"""Plaid to Firefly III integration"""

import os
import ast

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from dotenv import load_dotenv

import const 
import logging

from exceptions import Plaid2FireflyConnectionError, Plaid2FireflyError, Plaid2FireflyTimeoutError
from plaid import PlaidClient

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
_LOGGER = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """This is the root endpoint. For development purposes only."""

    env_vars = {}
    env_file_path = Path(".env")
    if env_file_path.exists():
        with open(env_file_path, "r") as env_file:
            for line in env_file:
                key, value = line.strip().split("=")
                env_vars[key] = value
    _LOGGER.info(f"Loaded environment variables: {env_vars}")

    if "PLAID_PUBLIC_TOKEN" not in env_vars and "PLAID_ACCESS_TOKEN" not in env_vars:
        _LOGGER.info("Neither PLAID_PUBLIC_TOKEN nor PLAID_ACCESS_TOKEN is set in the environment variables.")

    return Path("templates/index.html").read_text()


@app.post("/update-config")
async def update_config(request: Request):
    """Update the config file"""
    try:
        config_data = await request.json()
        with open(".env", "w") as env_file:
            for key, value in config_data.items():
                env_file.write(f"{key.upper()}={value}\n")

        _LOGGER.info("Configuration successfully written to .env file.")
        return {"message": "Configuration updated successfully."}
    except Exception as e:
        _LOGGER.error(f"Failed to update configuration: {e}")
        return {"error": "Failed to update configuration."}, 500


@app.get("/config")
async def get_config():
    """Get the config file"""
    try:
        config = {}
        with open(".env", "r") as env_file:
            for line in env_file:
                key, value = line.strip().split("=")
                config[key] = value

        country_codes_raw = config.get("COUNTRY_CODES", "[]")
        try:
            config["COUNTRY_CODES"] = ast.literal_eval(country_codes_raw)
            if not isinstance(config["COUNTRY_CODES"], list):
                raise ValueError("COUNTRY_CODES must be a list")
        except (ValueError, SyntaxError):
            config["COUNTRY_CODES"] = []

        _LOGGER.info("Configuration successfully read from .env file.")
        return config
    except Exception as e:
        _LOGGER.error(f"Failed to read configuration: {e}")
        return {"error": "Failed to read configuration."}, 500

@app.get("/get-country-codes")
async def get_country_codes():
    """Show the current allowed country codes"""
    _LOGGER.info("Getting country codes")
    return {"allowed_country_codes": const.ALLOWED_COUNTRY_CODES}

@app.get("/get-public-token")
async def get_public_token():
    """Get the public token"""
    _LOGGER.info("Getting public token")
    plaid = PlaidClient(
        plaid_client_id=os.getenv("PLAID_CLIENT_ID"),
        plaid_secret=os.getenv("PLAID_SECRET"),
        plaid_env=os.getenv("PLAID_ENV", "production"),
    )
    try:
        public_token = await plaid.create_public_token()
        return {"public_token": public_token}
    except Plaid2FireflyConnectionError as e:
        _LOGGER.exception(f"Connection error while getting public token: {e}")
        return {"error": "Connection error", "details": str(e)}, 500
    except Plaid2FireflyTimeoutError as e:
        _LOGGER.exception(f"Timeout error while getting public token: {e}")
        return {"error": "Timeout error", "details": str(e)}, 500
    except Plaid2FireflyError as e:
        _LOGGER.exception(f"Error while getting public token: {e}")
        return {"error": "Plaid API error", "details": str(e)}, 500
    except Exception as e:
        _LOGGER.exception(f"Unexpected error while getting public token: {e}")
        return {"error": "Unexpected error", "details": str(e)}, 500


