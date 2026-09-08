"""Private S3 boundary. No filesystem paths, public ACLs or raw provider errors."""
import re
from typing import Protocol
from .config import Settings

KEY = re.compile(r"^assets/[a-f0-9]{32}/[a-f0-9]{32}/[a-z0-9][a-z0-9._-]{0,100}$")


def validate_key(key: str) -> str:
    if not KEY.fullmatch(key) or ".." in key:
        raise ValueError("Invalid private object key")
    return key


class ObjectStore(Protocol):
    def healthy(self) -> bool: ...
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class S3Store:
    def __init__(self, config: Settings):
        import boto3
        from botocore.config import Config
        self.bucket = config.s3_bucket
        self.client = boto3.client(
            "s3", endpoint_url=config.s3_endpoint, region_name=config.s3_region,
            aws_access_key_id=config.s3_access_key.get_secret_value(),
            aws_secret_access_key=config.s3_secret_key.get_secret_value(),
            config=Config(signature_version="s3v4", connect_timeout=2, read_timeout=3,
                          retries={"max_attempts": 0}, s3={"addressing_style": "path"}),
        )

    def healthy(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=validate_key(key), Body=data,
                               ContentType=content_type)

    def get(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=validate_key(key))
        with response["Body"] as body:
            return body.read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=validate_key(key))
