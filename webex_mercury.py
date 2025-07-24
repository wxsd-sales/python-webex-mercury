import asyncio
import base64
import json
import logging
from typing import Dict, Any, Callable, Optional
import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)

class WebexMercuryClient:
    """
    A Python client for connecting to Webex Mercury service for real-time events.
    
    This replicates the core functionality of webexSdk.internal.mercury from the JS SDK.
    """
    
    def __init__(self, access_token: str):
        """
        Initialize the Mercury client with a Webex access token.
        
        Args:
            access_token: Valid Webex access token (bot or user token)
        """
        self.access_token = access_token
        self.websocket = None
        self.mercury_url = None
        self.url = None
        self.event_handlers = {}
        self.is_connected = False
        self.session = None
        self.presence_subscriptions = set()  # Track active presence subscriptions
        
        # Webex WDM (Device Manager) endpoints - internal endpoints used by JS SDK
        self.wdm_base_url = "https://wdm-r.wbx2.com/wdm/api/v1"
        self.mercury_registration_url = f"{self.wdm_base_url}/devices?includeUpstreamServices=all"
        self.apheleia_base_url = "https://apheleia-r.wbx2.com/apheleia/api/v1"
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        if self.session:
            await self.session.close()
    
    async def authenticate_and_discover(self) -> Dict[str, Any]:
        """
        Authenticate with Webex and discover Mercury service endpoints.
        
        Returns:
            Device registration response containing Mercury WebSocket URL
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Register device to get Mercury connection details
        # Using WDM-specific device registration format
        device_data = {
            "deviceName": "python-webex-mercury-client",
            "deviceType": "WEB",
            "localizedModel": "python-webex-mercury-client",
            "model": "python-webex-mercury-client",
            "name": "python-webex-mercury-client",
            "systemName": "python-webex-mercury-client",
            "systemVersion": "1.0.0"
        }
        
        try:
            async with self.session.post(
                self.mercury_registration_url,
                headers=headers,
                json=device_data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Device registration failed: {response.status} - {error_text}")
                
                registration_data = await response.json()
                # Extract Mercury WebSocket URL and device info
                self.mercury_url = registration_data.get("webSocketUrl")
                self.url = registration_data.get("url")
                
                if not self.mercury_url:
                    raise Exception("No Mercury WebSocket URL found in registration response")
                
                logger.info(f"Device registered successfully. Mercury URL: {self.mercury_url}")
                logger.info(f"Device registered successfully. URL: {self.url}")
                return registration_data
                
        except Exception as e:
            logger.error(f"Authentication and discovery failed: {e}")
            raise
    
    async def connect(self) -> bool:
        """
        Connect to Mercury WebSocket service.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # First authenticate and discover Mercury endpoint
            await self.authenticate_and_discover()
            
            if not self.mercury_url:
                raise Exception("No Mercury URL available")
            
            # Prepare WebSocket headers
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            # Connect to Mercury WebSocket
            logger.info(f"Connecting to Mercury: {self.mercury_url}")
            self.websocket = await websockets.connect(
                self.mercury_url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            logger.info("Mercury WebSocket connected successfully")
            
            # Start message handling loop
            asyncio.create_task(self._handle_messages())
            
            return True
            
        except Exception as e:
            logger.error(f"Mercury connection failed: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Mercury WebSocket."""
        self.is_connected = False
        
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("Mercury WebSocket disconnected")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.websocket = None
    
    def on(self, event_name: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Register an event handler for a specific Mercury event.
        
        Args:
            event_name: Name of the event (e.g., 'telephony_calls.received')
            handler: Function to call when event is received
        """
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        
        self.event_handlers[event_name].append(handler)
        logger.info(f"Registered handler for event: {event_name}")
    
    def off(self, event_name: str, handler: Optional[Callable] = None):
        """
        Remove event handler(s) for a specific event.
        
        Args:
            event_name: Name of the event
            handler: Specific handler to remove (if None, removes all handlers for event)
        """
        if event_name in self.event_handlers:
            if handler:
                try:
                    self.event_handlers[event_name].remove(handler)
                    logger.info(f"Removed specific handler for event: {event_name}")
                except ValueError:
                    logger.warning(f"Handler not found for event: {event_name}")
            else:
                self.event_handlers[event_name] = []
                logger.info(f"Removed all handlers for event: {event_name}")
    
    async def _handle_messages(self):
        """
        Internal method to handle incoming WebSocket messages.
        """
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._process_event(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse WebSocket message: {e}")
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    
        except ConnectionClosed:
            logger.info("Mercury WebSocket connection closed")
            self.is_connected = False
        except WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Unexpected error in message handler: {e}")
            self.is_connected = False
    
    async def _process_event(self, data: Dict[str, Any]):
        """
        Process an incoming Mercury event and trigger appropriate handlers.
        
        Args:
            data: Event data from Mercury
        """
        try:
            # Extract event type - Mercury events typically have a 'data' structure
            event_type = data.get("data", {}).get("eventType")
            
            if not event_type:
                # Some events might have different structure
                event_type = data.get("type") or data.get("eventType")
            
            if event_type:
                # Call registered handlers for this event type
                handlers = self.event_handlers.get(event_type, [])
                for handler in handlers:
                    try:
                        # Call handler - could be sync or async
                        if asyncio.iscoroutinefunction(handler):
                            await handler(data)
                        else:
                            handler(data)
                    except Exception as e:
                        logger.error(f"Error in event handler for {event_type}: {e}")
                
                # Also trigger handlers for wildcard patterns
                for pattern, pattern_handlers in self.event_handlers.items():
                    if pattern != event_type and self._event_matches_pattern(event_type, pattern):
                        for handler in pattern_handlers:
                            try:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(data)
                                else:
                                    handler(data)
                            except Exception as e:
                                logger.error(f"Error in pattern handler for {pattern}: {e}")
            
            # Log the event for debugging
            logger.debug(f"Processed Mercury event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error processing Mercury event: {e}")
    
    def _event_matches_pattern(self, event_type: str, pattern: str) -> bool:
        """
        Check if an event type matches a pattern (simple wildcard support).
        
        Args:
            event_type: Actual event type
            pattern: Pattern to match against
        
        Returns:
            True if event matches pattern
        """
        # Simple pattern matching - could be extended for more complex patterns
        if "*" in pattern:
            pattern_parts = pattern.split("*")
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts
                return event_type.startswith(prefix) and event_type.endswith(suffix)
        
        return event_type == pattern
    
    async def send_message(self, message: Dict[str, Any]):
        """
        Send a message to Mercury WebSocket.
        
        Args:
            message: Message data to send
        """
        if not self.is_connected or not self.websocket:
            raise Exception("Not connected to Mercury")
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.debug("Message sent to Mercury")
        except Exception as e:
            logger.error(f"Failed to send message to Mercury: {e}")
            raise
    
    @property
    def connected(self) -> bool:
        """Check if Mercury connection is active."""
        return self.is_connected and self.websocket is not None
    
    def get_decoded_id(self, api_id: str) -> str:
        """Base64 Decodes an API ID and returns the ID often used by Webex microservices, such as Apheleia/Presence"""
        try:
            decoded_bytes = base64.b64decode(api_id + "==")
            decoded_string = decoded_bytes.decode('utf-8')
            id = decoded_string.rsplit("/",1)[1]
            return id
        except Exception as e:
            logger.error(f"Failed to decode API ID: {e}")
            raise

    # Presence functionality
    async def subscribe_to_presence(self, user_id: str, ttl: int = 600) -> bool:
        """
        Subscribe to presence updates for a specific user.
        
        Args:
            user_id: Webex user ID to subscribe to
            ttl: Time to live for subscription in seconds (default 600 = 10 minutes)
            
        Returns:
            Dictionary containing presence and subscription information
        """

        if not self.session:
            self.session = aiohttp.ClientSession()

        if not self.url or not self.connected:
            raise Exception(f"Mercury connection must be open")
            
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Cisco-Device-Url": self.url
        }
        
        presence_data = {
            "subjects" : [user_id],
            "subscriptionTtl": ttl,
            "includeStatus":True
        }
        
        try:
            async with self.session.post(
                f"{self.apheleia_base_url}/subscriptions",
                headers=headers,
                json=presence_data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Presence subscribe failed: {response.status} - {error_text}")
                
                subscribe_data = await response.json()
                return subscribe_data
                
        except Exception as e:
            logger.error(f"Presence subscribe failed: {e}")
            raise

    
    async def unsubscribe_from_presence(self, user_id: str) -> bool:
        """
        Unsubscribe from presence updates for a specific user.
        
        Args:
            user_id: Webex user ID to unsubscribe from
            
        Returns:
            True if unsubscription successful, False otherwise
        """

        unsubscribe = await self.subscribe_to_presence(user_id, 0)
        return unsubscribe
    
    
    async def get_presence_status(self, user_ids: list) -> Dict[str, Any]:
        """
        Get current presence status for a list of users.
        
        Args:
            user_ids: List of Webex user IDs to get presence for
            
        Returns:
            Dictionary containing presence information
        """
        
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        presence_data = {
            "subjects" : user_ids
        }
        
        try:
            async with self.session.post(
                f"{self.apheleia_base_url}/compositions",
                headers=headers,
                json=presence_data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Get Presence status failed: {response.status} - {error_text}")
                
                status_data = await response.json()
                return status_data
                
        except Exception as e:
            logger.error(f"Get Presence status failed: {e}")
            raise



