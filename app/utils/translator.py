import base64
import aiohttp
from http import HTTPStatus

async def download_image_url(logger, image_url: str) -> str:
    """
    Download an image from a URL and return the base64 encoded string
    """

    # if the image url is a data url, return it as is
    if image_url.startswith("data:"):
        return image_url
    
    async with aiohttp.ClientSession() as session:
        async with session.head(image_url) as response:
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                log_error_msg = f"Failed to fetch file metadata from URL: {error_text}"
                logger.error(log_error_msg)
                raise RuntimeError(log_error_msg)

            mime_type = response.headers.get("Content-Type", "")
            file_size = int(response.headers.get("Content-Length", 0))
            if file_size > 10 * 1024 * 1024:
                log_error_msg = f"Image file size is too large: {file_size} bytes"
                logger.error(log_error_msg)
                raise RuntimeError(log_error_msg)

        async with session.get(image_url) as response:
            # return format is data:mime_type;base64,base64_data
            return f"data:{mime_type};base64,{base64.b64encode(await response.read()).decode('utf-8')}"
