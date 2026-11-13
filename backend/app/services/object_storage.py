from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings


@lru_cache(maxsize=1)
def get_storage_client() -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key.get_secret_value(),
        aws_secret_access_key=settings.object_storage_secret_key.get_secret_value(),
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def ensure_bucket() -> None:
    client = get_storage_client()
    try:
        client.head_bucket(Bucket=settings.object_storage_bucket)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        try:
            client.create_bucket(Bucket=settings.object_storage_bucket)
        except ClientError as create_error:
            code = str(create_error.response.get("Error", {}).get("Code", ""))
            if code != "BucketAlreadyOwnedByYou":
                raise


def put_object(*, object_key: str, content: bytes, content_type: str) -> None:
    ensure_bucket()
    get_storage_client().put_object(
        Bucket=settings.object_storage_bucket,
        Key=object_key,
        Body=content,
        ContentLength=len(content),
        ContentType=content_type,
    )


def get_object(*, object_key: str) -> bytes:
    response = get_storage_client().get_object(
        Bucket=settings.object_storage_bucket,
        Key=object_key,
    )
    body = response["Body"]
    try:
        return body.read()
    finally:
        body.close()


def delete_object(*, object_key: str) -> None:
    get_storage_client().delete_object(
        Bucket=settings.object_storage_bucket,
        Key=object_key,
    )
