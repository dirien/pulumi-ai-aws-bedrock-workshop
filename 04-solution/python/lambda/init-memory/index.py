import json
import logging
from datetime import datetime, timezone

import boto3


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def handler(event, _context):
    LOGGER.info("Received event: %s", json.dumps(event))

    memory_id = event["memoryId"]
    region = event.get("region")

    client = boto3.client("bedrock-agentcore", region_name=region)

    preferences_text = (
        "When the weather is good I love hiking, beach volleyball, outdoor "
        "picnics, farmers markets, gardening, photography, and bird watching. "
        "If the weather is just OK I prefer walking tours, outdoor dining, "
        "park visits, and museums. When the weather is poor I'd rather visit "
        "indoor museums, go shopping, eat at restaurants, or watch movies."
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    response = client.create_event(
        memoryId=memory_id,
        actorId="user123",
        sessionId="session456",
        eventTimestamp=timestamp,
        # A conversational event, not an opaque blob: the USER_PREFERENCE
        # strategy only extracts long-term records from conversation turns.
        payload=[
            {
                "conversational": {
                    "role": "USER",
                    "content": {"text": preferences_text},
                }
            }
        ],
    )

    event_id = response.get("eventId", "unknown")
    LOGGER.info("Memory initialized with event %s", event_id)

    return {
        "memoryId": memory_id,
        "eventId": event_id,
        "status": "initialized",
    }
