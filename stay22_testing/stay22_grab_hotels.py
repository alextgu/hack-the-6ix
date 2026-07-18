"""

stay22_grab_hotels.py

This script searches for hotels based on given location (city, country)

"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

STAY22_API_KEY = os.environ["STAY22_API_KEY"]
BASE_URL = "https://api.stay22.com/v2"


def get_nearby_hotels(city: str, page_size: int = 10, page: int = 1) -> list[dict]:
    """Fetch hotels near a given city from the Stay22 accommodations API."""
    response = requests.get(
        f"{BASE_URL}/accommodations",
        headers={"X-API-KEY": STAY22_API_KEY},
        params={"address": city, "pageSize": page_size, "page": page},
    )
    response.raise_for_status()
    return response.json()["results"]


if __name__ == "__main__":
    hotels = get_nearby_hotels("Japan")
    for hotel in hotels:
        print(hotel["name"], "-", hotel["location"]["address"])
