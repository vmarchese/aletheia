"""Authentication server for secure password entry via web browser."""

import asyncio
import logging
import secrets
import webbrowser
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel


class PasswordPrompt(BaseModel):
    """Password prompt details."""

    token: str
    prompt_text: str
    timeout_seconds: int = 300  # 5 minutes default


class AuthServer:
    """
    Web-based authentication server for secure password entry.

    Allows users to enter passwords through a web browser instead of
    command-line prompts, which is more secure and user-friendly.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8766):
        """Initialize auth server."""
        self.host = host
        self.port = port
        self.app = FastAPI(title="Aletheia Auth Server")
        self.logger = logging.getLogger("aletheia.auth")

        # Store pending password prompts
        self._pending_prompts: dict[str, PasswordPrompt] = {}
        self._password_results: dict[str, Optional[str]] = {}
        self._result_events: dict[str, asyncio.Event] = {}

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup FastAPI routes."""

        @self.app.get("/auth/{token}", response_class=HTMLResponse)
        async def auth_page(token: str) -> HTMLResponse:
            """Display password entry form."""
            prompt = self._pending_prompts.get(token)
            if not prompt:
                raise HTTPException(status_code=404, detail="Invalid or expired token")

            return HTMLResponse(content=self._get_auth_html(prompt))

        @self.app.post("/auth/{token}")
        async def submit_password(token: str, password: str = Form(...)) -> RedirectResponse:
            """Handle password submission."""
            prompt = self._pending_prompts.get(token)
            if not prompt:
                raise HTTPException(status_code=404, detail="Invalid or expired token")

            # Store result and signal completion
            self._password_results[token] = password
            if token in self._result_events:
                self._result_events[token].set()

            # Clean up prompt
            self._pending_prompts.pop(token, None)

            return RedirectResponse(url=f"/auth/{token}/success", status_code=303)

        @self.app.get("/auth/{token}/success", response_class=HTMLResponse)
        async def success_page(token: str) -> HTMLResponse:
            """Display success page."""
            return HTMLResponse(content=self._get_success_html())

        @self.app.get("/health")
        async def health() -> dict[str, str]:
            """Health check endpoint."""
            return {"status": "healthy"}

    async def prompt_password(
        self,
        prompt_text: str = "Enter session password:",
        timeout_seconds: int = 300,
    ) -> Optional[str]:
        """
        Prompt user for password via web browser.

        Args:
            prompt_text: Text to display in the prompt
            timeout_seconds: Maximum time to wait for password entry

        Returns:
            The entered password, or None if cancelled/timeout
        """
        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Create prompt
        prompt = PasswordPrompt(
            token=token,
            prompt_text=prompt_text,
            timeout_seconds=timeout_seconds,
        )
        self._pending_prompts[token] = prompt

        # Create event for result
        event = asyncio.Event()
        self._result_events[token] = event

        # Open browser
        url = f"http://{self.host}:{self.port}/auth/{token}"
        self.logger.info(f"Opening browser for password entry: {url}")
        webbrowser.open(url)

        # Wait for result with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            password = self._password_results.get(token)
            return password
        except asyncio.TimeoutError:
            self.logger.warning("Password prompt timed out")
            return None
        finally:
            # Clean up
            self._pending_prompts.pop(token, None)
            self._password_results.pop(token, None)
            self._result_events.pop(token, None)

    def _get_auth_html(self, prompt: PasswordPrompt) -> str:
        """Get HTML for password entry form."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aletheia Authentication</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-lg max-w-md w-full">
        <div class="mb-6">
            <h1 class="text-2xl font-bold text-gray-900 mb-2">Aletheia Authentication</h1>
            <p class="text-gray-600">{prompt.prompt_text}</p>
        </div>

        <form method="post" action="/auth/{prompt.token}" class="space-y-4">
            <div>
                <label for="password" class="block text-sm font-medium text-gray-700 mb-2">
                    Password
                </label>
                <input
                    type="password"
                    id="password"
                    name="password"
                    class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter your password"
                    autofocus
                    required
                />
            </div>

            <div class="flex space-x-3">
                <button
                    type="submit"
                    class="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    Submit
                </button>
                <button
                    type="button"
                    onclick="window.close()"
                    class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500"
                >
                    Cancel
                </button>
            </div>
        </form>

        <div class="mt-6 text-xs text-gray-500 text-center">
            <p>This prompt will expire in {prompt.timeout_seconds // 60} minutes</p>
            <p class="mt-1">🔒 Your password is transmitted securely over localhost</p>
        </div>
    </div>

    <script>
        // Auto-submit on Enter key
        document.getElementById('password').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{
                e.target.form.submit();
            }}
        }});
    </script>
</body>
</html>
        """

    def _get_success_html(self) -> str:
        """Get HTML for success page."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authentication Complete</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-lg max-w-md w-full text-center">
        <div class="mb-4">
            <svg class="w-16 h-16 mx-auto text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
            </svg>
        </div>

        <h1 class="text-2xl font-bold text-gray-900 mb-2">Authentication Complete</h1>
        <p class="text-gray-600 mb-6">Your password has been submitted successfully.</p>

        <button
            onclick="window.close()"
            class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
            Close Window
        </button>

        <p class="mt-6 text-sm text-gray-500">
            You can now return to your terminal.
        </p>
    </div>

    <script>
        // Auto-close after 3 seconds
        setTimeout(() => {
            window.close();
        }, 3000);
    </script>
</body>
</html>
        """

    async def start(self) -> None:
        """Start the auth server."""
        import uvicorn

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",  # Less verbose
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main() -> None:
    """Main entry point for testing auth server."""
    logging.basicConfig(level=logging.INFO)

    auth = AuthServer()

    # Start server in background
    server_task = asyncio.create_task(auth.start())

    # Wait a bit for server to start
    await asyncio.sleep(1)

    # Test password prompt
    print("Testing password prompt...")
    password = await auth.prompt_password("Enter test password:", timeout_seconds=60)

    if password:
        print(f"Received password: {'*' * len(password)}")
    else:
        print("No password received (timeout or cancelled)")

    # Cancel server
    server_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
