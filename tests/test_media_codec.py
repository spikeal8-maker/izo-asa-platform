"""Exercise the real disposable decoder; never opens arbitrary formats or URLs."""
import io
import pytest
from PIL import Image
from izo.media.codec import decode, rewrite, LimitedBuffer
from izo.media.schemas import MediaError
from test_media import image_bytes


@pytest.mark.parametrize('fmt,mime', [('PNG','image/png'),('JPEG','image/jpeg'),('WEBP','image/webp')])
def test_allowed_images_run_in_child_and_rewrite_to_png(fmt, mime):
    data = image_bytes(fmt)
    image = decode(data, mime, 8, 6, 100000)
    with Image.open(io.BytesIO(image.data)) as im:
        im.load()
        assert im.format=='PNG' and im.size==(8,6) and not im.info


@pytest.mark.parametrize('data,mime,w,h', [(b'<svg><script/></svg>','image/png',8,6),
    (b'<html>not-an-image</html>','image/png',8,6),
    (image_bytes()[:40],'image/png',8,6), (image_bytes(),'image/jpeg',8,6),
    (image_bytes(),'image/png',9,6), (image_bytes('GIF'),'image/png',8,6)])
def test_bad_images_fail_closed_in_child(data, mime, w, h):
    with pytest.raises(MediaError) as exc:
        decode(data, mime, w, h, 100000)
    assert exc.value.code=='invalid_image'


def test_encoder_output_bound_is_enforced():
    with pytest.raises(ValueError):
        rewrite(image_bytes(), 'image/png', 8, 6, 20)
    buf = LimitedBuffer(5)
    with pytest.raises(ValueError): buf.write(b'123456')


def test_appended_content_and_metadata_are_removed():
    data = image_bytes(metadata=True) + b'<script>private</script>'
    result = decode(data,'image/png',8,6,100000)
    assert b'script' not in result.data and b'do-not-publish' not in result.data


def test_animation_rejected():
    stream=io.BytesIO()
    with Image.new('RGB',(8,6),(1,2,3)) as a, Image.new('RGB',(8,6),(4,5,6)) as b:
        a.save(stream,format='PNG',save_all=True,append_images=[b],duration=100,loop=0)
    with pytest.raises(MediaError): decode(stream.getvalue(),'image/png',8,6,100000)


def test_decoder_does_not_inherit_server_secrets(monkeypatch):
    import struct
    from types import SimpleNamespace
    from izo.media import codec
    image=image_bytes()
    def invoke(command, **kw):
        assert 'IZO_PG_PASSWORD' not in kw['env'] and 'IZO_S3_SECRET_KEY' not in kw['env']
        assert set(kw['env'])=={'PATH','PYTHONPATH','PYTHONNOUSERSITE','AWS_EC2_METADATA_DISABLED'}
        assert 'shell' not in kw and kw['timeout']==20
        return SimpleNamespace(returncode=0,stdout=struct.pack('>II',8,6)+image)
    monkeypatch.setenv('IZO_PG_PASSWORD','synthetic-do-not-inherit')
    monkeypatch.setattr(codec.subprocess,'run',invoke)
    assert decode(image,'image/png',8,6,100000).width==8
