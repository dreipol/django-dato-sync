import base64
import random
import string

from django.core.management import BaseCommand

_RANDOM_PASSWORD_LENGTH = 32


class Command(BaseCommand):

    def handle(self, *args, **options):
        username = input("Username: ")
        password = input("Password (empty to generate random password): ")
        if not password:
            alphabet = string.ascii_letters + string.digits + "-_+\"*%&/()=?.,"
            password = "".join(random.choice(alphabet) for _ in range(_RANDOM_PASSWORD_LENGTH))

        raw = username + ":" + password
        b64string = base64.b64encode(raw.encode()).decode()
        print("Dato Config:")
        print("  Endpoint: https://<your-domain>/dato-sync/sync/")
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print("Django Config:")
        print(f"  DATO_SYNC_WEBHOOK_EXPECTED_AUTH=\"Basic {b64string}\"")