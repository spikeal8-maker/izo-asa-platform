"""Reuse configured private S3 transport; bounded reads, no public ACL or URLs."""
from ..storage import S3Store, validate_key
from .schemas import MAX_OUTPUT


class MediaStore(S3Store):
    def read(self, key: str, maximum: int) -> bytes:
        if type(maximum) is not int or not 0 < maximum <= MAX_OUTPUT:
            raise ValueError("Invalid object bound")
        response = self.client.get_object(Bucket=self.bucket, Key=validate_key(key))
        with response["Body"] as body:
            if response.get("ContentLength", maximum + 1) > maximum:
                raise ValueError("Object exceeds declared bound")
            data = body.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError("Object exceeds declared bound")
        return data
