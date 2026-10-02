import os
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode
from dotenv import load_dotenv


load_dotenv(override=True)

TOKEN = os.getenv("SHOPIER_ACCESS_TOKEN", "").strip()
BASE_URL = "https://api.shopier.com/v1"


def call_shopier(path, params=None):
    url = BASE_URL + path

    if params:
        url += "?" + urlencode(params)

    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
            "User-Agent": "semih-akvaryum/1.0",
        },
    )

    print("\n---------------------------")
    print("TEST:", path)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")

            print("STATUS:", response.status)
            print(body[:3000])

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        print("STATUS:", exc.code)
        print("BODY:", body[:3000])

    except Exception as exc:
        print(
            "ERROR:",
            type(exc).__name__,
            str(exc),
        )


print("TOKEN FOUND:", bool(TOKEN))
print("TOKEN LENGTH:", len(TOKEN))


# 1 - Ürünleri test et
call_shopier(
    "/products"
)


call_shopier("/products")

call_shopier("/products/50488190")

call_shopier(
    "/orders",
    {
        "dateStart": "2026-01-01T00:00:00Z",
        "dateEnd": "2026-10-03T23:59:59Z",
        "limit": 10,
    },
)