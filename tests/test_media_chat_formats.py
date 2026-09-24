"""Chat-supported image formats reuse the canonical private Media pipeline."""
import io

import pytest
from PIL import Image

from test_media import env, finish, image_bytes


@pytest.mark.parametrize(('fmt', 'content_type'), [
    ('PNG', 'image/png'),
    ('JPEG', 'image/jpeg'),
    ('WEBP', 'image/webp'),
    ('GIF', 'image/gif'),
])
def test_supported_chat_image_formats_are_canonicalized_to_private_png(
        env, fmt, content_type):
    data = image_bytes(fmt=fmt)
    result, _, _ = finish(env, data, content_type=content_type)
    stored = env[-1].data[next(iter(env[-1].data))]
    assert result.status == 'ready'
    assert stored.startswith(b'\x89PNG\r\n\x1a\n')
    with Image.open(io.BytesIO(stored)) as image:
        image.load()
        assert image.size == (8, 6)
