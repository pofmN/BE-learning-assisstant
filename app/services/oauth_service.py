"""
OAuth authentication service for third-party providers (stateless for cloud).
"""
import logging
import secrets
from typing import Optional, Dict, Any
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.security import create_access_token, decode_token
from datetime import timedelta

logger = logging.getLogger(__name__)

class OAuthService:
    """ Service for handling OAuth authentication (stateless). """

    @staticmethod
    def generate_state_token() -> str:
        """Generate a secure state token for CSRF protection."""
        # Create a JWT token with short expiration for state
        state_token = create_access_token(
            subject="oauth_state",
            expires_delta=timedelta(minutes=10),
            extra_claims={"type": "oauth_state", "nonce": secrets.token_urlsafe(16)}
        )
        return state_token
    
    @staticmethod
    def verify_state_token(state: str) -> bool:
        """Verify the state token is valid."""
        try:
            payload = decode_token(state)
            return payload and payload.get("type") == "oauth_state" # type: ignore
        except Exception as e:
            logger.error(f"State token verification failed: {e}")
            return False
    
    @staticmethod
    def generate_google_auth_url() -> str:
        """
        Generate Google OAuth authorization URL (stateless).
        
        Returns:
            Authorization URL to redirect user to
        """
        state = OAuthService.generate_state_token()
        
        params = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        logger.info("Generated Google OAuth authorization URL")
        return auth_url
    
    @staticmethod
    async def exchange_code_for_token(code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from Google
            
        Returns:
            Token response from Google
            
        Raises:
            HTTPException: If token exchange fails
        """
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()
                token = response.json()
                logger.info("Successfully exchanged code for token")
                return token
        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code"
            )
    
    @staticmethod
    async def get_google_user_info(token: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch user information from Google using access token.
        
        Args:
            token: OAuth token response
            
        Returns:
            User information dictionary
            
        Raises:
            HTTPException: If unable to fetch user info
        """
        try:
            access_token = token.get('access_token')
            if not access_token:
                raise ValueError("No access token in response")
            
            headers = {'Authorization': f"Bearer {access_token}"}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    'https://www.googleapis.com/oauth2/v2/userinfo',
                    headers=headers
                )
                response.raise_for_status()
                user_info = response.json()
                
                logger.info(f"Successfully fetched Google user info for email: {user_info.get('email')}")
                return user_info
            
        except Exception as e:
            logger.error(f"Failed to fetch Google user info: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch user information from Google"
            )
        
    @staticmethod
    def validate_oauth_user_data(user_info: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate and extract required fields from OAuth user info.
        
        Args:
            user_info: Raw user info from OAuth provider
            
        Returns:
            Validated user data
            
        Raises:
            HTTPException: If required fields are missing
        """
        email = user_info.get('email')
        if not email:
            logger.warning("OAuth user info missing email")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by OAuth provider"
            )
        
        return {
            'email': email,
            'full_name': user_info.get('name', ''),
            'avatar_url': user_info.get('picture', ''),
            'oauth_id': user_info.get('id', user_info.get('sub', '')),
        }