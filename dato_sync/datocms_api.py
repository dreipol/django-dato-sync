from django.conf import settings
import requests
from requests.auth import AuthBase


class DatoException(Exception):
    pass


class DatoTokenAuth(AuthBase):
    """Implements a token authentication scheme."""

    def __init__(self, token, environment):
        self.token = token
        self.environment = environment

    def __call__(self, request):
        """Attach an API token to the Authorization header."""
        request.headers["Authorization"] = f"Bearer {self.token}"
        request.headers["Content-Type"] = "application/json"
        request.headers["Accept"] = "application/json"
        request.headers["X-Environment"] = self.environment
        return request


def fetch_datocms_content(language: str, query: str) -> dict:
    api_token = settings.DATOCMS_API_TOKEN
    api_url = f"{settings.DATOCMS_API_URL}/"
    environment = settings.DATOCMS_ENVIRONMENT
    variables = {"locale": language}
    response = requests.post(
        api_url, auth=DatoTokenAuth(api_token, environment), json={"query": query, "variables": variables}
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("errors"):
            raise DatoException("\n" + "\n".join([f"- {error["message"]}" for error in data["errors"]]))

        return data.get("data")
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return {}
