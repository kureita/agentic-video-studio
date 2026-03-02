import boto3
import os
import sys

def test_s3():
    # Print out what boto3 thinks the credentials are
    s3 = boto3.client('s3')
    creds = s3._request_signer._credentials
    if creds:
        print(f"Boto3 resolved Access Key: {creds.access_key}")
    else:
        print("No creds resolved")
test_s3()
