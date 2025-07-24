# python-webex-mercury

This python module allows you to create a connection to Webex Mercury in order to listen for events.  An incomprehensive list of events that can be listened for can be found [here](#tested-mercury-events).

### Prerequisites & Dependencies: 
python 3.8.3 or higher

## Getting Started
After you clone this repo, or copy the [webex_mercury.py](webex_mercury.py) file, you can create a very simple mercury client that listens for Webex Message events, including read receipts like this:

```python
import asyncio
from webex_mercury import WebexMercuryClient

async def main():
    ACCESS_TOKEN = "your_bearer_token"
    
    async with WebexMercuryClient(ACCESS_TOKEN) as mercury_client:
        
        mercury_client.on('conversation.activity', lambda event: 
            print(f"Message received: {event}"))

        # Connect to Mercury
        if await mercury_client.connect():
            print("Connected to Mercury successfully!")

            # Keep the connection alive and listen for events
            try:
                while mercury_client.connected:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("Shutting down...")
            print("Mercury no longer connected")
        else:
            print("Failed to connect to Mercury")

asyncio.run(main())
```

## Webex Calling Agent Calls Received Example

```python
import asyncio
from webex_mercury import WebexMercuryClient

async def main():
    ACCESS_TOKEN = "your_bearer_token"
    
    async with WebexMercuryClient(ACCESS_TOKEN) as mercury_client:
        
        # Event handlers
        def on_telephony_call(event):
            print(f"*** Telephony call event received ***: {event}")
        
        # Register handlers
        mercury_client.on('telephony_calls.received', on_telephony_call)

        # Connect to Mercury
        if await mercury_client.connect():
            print("Connected to Mercury successfully!")

            # Keep the connection alive and listen for events
            try:
                while mercury_client.connected:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("Shutting down...")
            print("Mercury no longer connected")
        else:
            print("Failed to connect to Mercury")

    
# Run the example
asyncio.run(main())
```

## Multiple Event Handlers + Presence Subscription 
This is the full example, also available as [example.py](example.py).

You must provide:
- An ```ACCESS_TOKEN```
- A ```USER_ID``` (different from the token owner, but in **the same org**)
    - ```USER_ID``` should be the Webex REST API ```personId```.
    - This example includes a helper function: ```get_decoded_id```, since Apeleia expects a decoded ID.
    - Mercury events of type ```apheleia.subscription_update``` automatically include the token owner, without a call to the function: ```subscribe_to_presence```

Presence API Usage
- Check Current Presence (No Mercury Connection required):
    - ```get_presence_status([user_id])```

- Subscribe to Presence (Requires Mercury Connection):
    - ```subscribe_to_presence(user_id, 600)```
    - 600 = Time-To-Live (TTL) for the subscription in seconds.

```python
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
``` 

## Tested Mercury Events
```
conversation.activity

apheleia.subscription_update

telephony_calls.answered
telephony_calls.bargedIn
telephony_calls.disconnected
telephony_calls.originating
telephony_calls.originated
telephony_calls.received
telephony_calls.resumed
telephony_calls.retrieved
telephony_calls.transferred

telephony_conference.created
telephony_conference.disconnected

convergedRecordings.created
convergedRecordings.deleted
convergedRecordings.updated
```

## License
All contents are licensed under the MIT license. Please see [license](LICENSE) for details.


## Disclaimer
<!-- Keep the following here -->  
 Everything included is for demo and Proof of Concept purposes only. Use of the site is solely at your own risk. This site may contain links to third party content, which we do not warrant, endorse, or assume liability for. These demos are for Cisco Webex usecases, but are not Official Cisco Webex Branded demos.
 
## Questions
Please contact the WXSD team at [wxsd@external.cisco.com](mailto:wxsd@external.cisco.com?subject=Python-Webex-Mercury) for questions. Or, if you're a Cisco internal employee, reach out to us on the Webex App via our bot (globalexpert@webex.bot). In the "Engagement Type" field, choose the "API/SDK Proof of Concept Integration Development" option to make sure you reach our team. 
