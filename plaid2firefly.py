"""Plaid to Firefly III integration"""

from logging import config
import os
import json
import ast
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from dotenv import load_dotenv
from yarl import URL

from config import Config
import const 
import logging

from exceptions import Plaid2FireflyConnectionError, Plaid2FireflyError, Plaid2FireflyTimeoutError
#from plaid import PlaidClient
import plaid
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
_LOGGER = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


config = Config("config.json")

@app.get("/", response_class=HTMLResponse)
async def index():
    """This is the root endpoint. For development purposes only."""

    _LOGGER.info(f"Loaded configuration: {config._config}")
    plaid_public_token = config.get("plaid_public_token")
    plaid_access_token = config.get("plaid_access_token")  

    if not plaid_public_token and not plaid_access_token:
        _LOGGER.info("Neither PLAID_PUBLIC_TOKEN nor PLAID_ACCESS_TOKEN is set in the configuration.")

    return Path("templates/index.html").read_text()


@app.post("/update-config")
async def update_config(request: Request):
    """Update the config file"""
    try:
        config_data = await request.json()
        config.update(config_data)  # Use the Config class to update the configuration

        _LOGGER.info("Configuration successfully updated.")
        return {"message": "Configuration updated successfully."}
    except Exception as e:
        _LOGGER.error(f"Failed to update configuration: {e}")
        return {"error": "Failed to update configuration."}, 500


@app.get("/config")
async def get_config():
    """Get the config file"""
    try:
        # Use the Config class to fetch the current configuration
        current_config = config._config
        _LOGGER.info("Configuration successfully read.")
        return current_config
    except Exception as e:
        _LOGGER.error(f"Failed to read configuration: {e}")
        return {"error": "Failed to read configuration."}, 500

@app.get("/get-country-codes")
async def get_country_codes():
    """Show the current allowed country codes"""
    _LOGGER.info("Getting country codes")
    return {"allowed_country_codes": const.ALLOWED_COUNTRY_CODES}

@app.get("/get-link-token")
async def get_link_token():
    """Get the link token"""
    _LOGGER.info("Getting link token")
    
    if config.get("plaid_env") == "sandbox":
        host = plaid.Environment.Sandbox
    else:
        host = plaid.Environment.Production

    configuration = plaid.Configuration(
        host=host,
        api_key={
            'clientId': config.get("plaid_client_id"),
            'secret': config.get("plaid_secret"),
            'plaidVersion': '2020-09-14'
        }
    )

    api_client = plaid.ApiClient(configuration)
    client = plaid_api.PlaidApi(api_client)

    try:
        request = LinkTokenCreateRequest(
            client_id=config.get("plaid_client_id"),
            secret=config.get("plaid_secret"),
            client_name="Plaid2Firefly",
            country_codes=list(map(lambda x: CountryCode(x), config.get("country_codes", []))),
            language="en",
            user=LinkTokenCreateRequestUser(
                client_user_id="Plaid2Firefly"
            ),
            products=list(map(lambda x: Products(x), ["transactions", "liabilities", "auth"])),
        )

        response = client.link_token_create(request)
        response = response.to_dict()
        _LOGGER.info("Response from Plaid: %s", response)
        config.set("link_token", response["link_token"])
        return {"response": response}

    except plaid.ApiException as e:
        _LOGGER.exception("Error creating link token")
        return {"error": "Error creating link token"}, 500

@app.get('/get-access-token')
async def get_access_token():
    """Get the access token"""
    _LOGGER.info("Getting access token")
    plaid_public_token = config.get("public_token")

    if not plaid_public_token:
        return {"error": "No public token provided"}, 400

    # Use the Plaid client to exchange the public token for an access token
    configuration = plaid.Configuration(
        host=plaid.Environment.Sandbox,
        api_key={
            'clientId': config.get("plaid_client_id"),
            'secret': config.get("plaid_secret"),
            'plaidVersion': '2020-09-14'
        }
    )

    api_client = plaid.ApiClient(configuration)
    client = plaid_api.PlaidApi(api_client)

    try:
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=plaid_public_token)
        response = client.item_public_token_exchange(exchange_request)
        response = response.to_dict()
        _LOGGER.info("Response from Plaid: %s", response)
        config.set("access_token", response["access_token"])
        return {"response": response}

    except plaid.ApiException as e:
        _LOGGER.exception("Error exchanging public token for access token")
        return {"error": "Error exchanging public token for access token"}, 500

