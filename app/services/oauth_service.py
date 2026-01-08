"""
OAuth authentication service for third-party providers.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from app.core.config import settings
from authlib.integrations.starlette_client import OAuth, OAuthError

logger = logging.getLogger(__name__)

oauth = OAuth()

oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    },
    redirect_uri=settings.GOOGLE_REDIRECT_URI
)

class OAuthService:
    """ Service for handling OAuth authentication. """

    @staticmethod
    def get_google_client():
        """ Get the Google OAuth client. """
        return oauth.google
    
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
            google = oauth.create_client('google')
            if not google:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Google OAuth client not configured"
                )
            resp = await google.get('https://www.googleapis.com/oauth2/v1/userinfo', token=token)
            resp.raise_for_status()
            user_info = resp.json()
            
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