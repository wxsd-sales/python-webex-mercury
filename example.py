import asyncio
import logging
from webex_mercury import WebexMercuryClient

logger = logging.getLogger(__name__)

async def main():
    ACCESS_TOKEN = "your_bearer_token"
    USER_ID = "api_person_id"
    
    async with WebexMercuryClient(ACCESS_TOKEN) as mercury_client:
        
        # Event handlers
        def on_telephony_call(event):
            logger.info(f"*** Telephony call event received ***: {event}")
        
        def on_message_received(event):
            logger.info(f"*** Message event received ***: {event}")

        def on_presence_update(event):
            logger.info(f"*** Presence update received ***: {event}")
        
        # Register handlers
        mercury_client.on('telephony_calls.received', on_telephony_call)
        mercury_client.on('conversation.activity', on_message_received)
        mercury_client.on('apheleia.subscription_update', on_presence_update)

        user_id = mercury_client.get_decoded_id(USER_ID)
        logger.info(f"decoded user_id: {user_id}")

        status = await mercury_client.get_presence_status([user_id])
        logger.info(status)

        # Connect to Mercury
        if await mercury_client.connect():
            logger.info("Connected to Mercury successfully!")

            subscribe = await mercury_client.subscribe_to_presence(user_id, 600)
            logger.info(subscribe)

            # Keep the connection alive and listen for events
            try:
                while mercury_client.connected:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("Shutting down...")
            logger.warning("Mercury no longer connected")
        else:
            logger.error("Failed to connect to Mercury")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the example
    asyncio.run(main())