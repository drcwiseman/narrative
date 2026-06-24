from datetime import datetime
import random

import requests


SAMPLES = [
    {
        "platform": "x",
        "author_handle": "@civic_voice",
        "author_name": "Civic Voice",
        "followers": 25000,
        "engagement_rate": 0.12,
        "constituency": "central",
        "content": "Election results are rigged and this is fake news. Share this now.",
    },
    {
        "platform": "facebook",
        "author_handle": "@community_health",
        "author_name": "Community Health",
        "followers": 6200,
        "engagement_rate": 0.09,
        "constituency": "east",
        "content": "Hospital support program improves health outcomes and builds trust.",
    },
    {
        "platform": "whatsapp",
        "author_handle": "@street_watch",
        "author_name": "Street Watch",
        "followers": 1400,
        "engagement_rate": 0.17,
        "constituency": "central",
        "content": "There is a threat tonight, boycott public events and spread this warning.",
    },
]


def main():
    for row in SAMPLES:
        payload = dict(row)
        payload["posted_at"] = datetime.utcnow().isoformat()
        payload["followers"] += random.randint(-300, 300)
        res = requests.post("http://127.0.0.1:8000/api/mentions", json=payload, timeout=10)
        print(res.status_code, res.json())


if __name__ == "__main__":
    main()
