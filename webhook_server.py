"""
Webhook Server — minimal Flask app that receives Stripe webhook events.

Run alongside the Streamlit app:
    python webhook_server.py

Listens on port 4242 by default.
In production, expose this via a reverse proxy (nginx, Caddy, etc.)
or use a tunnel (ngrok) for local development.

Stripe CLI local testing:
    stripe listen --forward-to localhost:4242/webhook
"""

from __future__ import annotations

import logging
import os

from flask import Flask, Response, request

from app.auth.db import init_db
from app.payments.stripe_client import construct_webhook_event
from app.payments.webhook import handle_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.before_request
def _init():
    init_db()


@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = construct_webhook_event(payload, sig_header)
    except ValueError as e:
        logger.error("Invalid webhook payload: %s", e)
        return Response("Invalid payload", status=400)
    except Exception as e:
        logger.error("Webhook signature verification failed: %s", e)
        return Response("Signature verification failed", status=400)

    try:
        handle_event(event)
    except Exception as e:
        logger.error("Error handling event %s: %s", event.get("type"), e)
        return Response("Handler error", status=500)

    return Response("OK", status=200)


@app.route("/health", methods=["GET"])
def health():
    return Response("OK", status=200)


if __name__ == "__main__":
    port = int(os.getenv("WEBHOOK_PORT", "4242"))
    logger.info("Webhook server starting on port %d", port)
    app.run(host="0.0.0.0", port=port)
