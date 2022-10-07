import os, re
import boto3, botocore.exceptions
from botocore.config import Config
from alt_proc.dict_ import dict_

try:
    import IPython
    from IPython.terminal.debugger import set_trace as ipython
except:
    pass


class NotFound(Exception):
    pass


class S3:

    def __init__(self):

        self.client = boto3.client(
            service_name='s3',
            config=Config(signature_version=botocore.UNSIGNED)
        )

    def parse_path(path):

        if not path.startswith('s3://'):
            raise Exception('Not valid s3 path', path)
        path = path[5:]
        path = path.replace('//', '/')
        pos = path.find('/')
        bucket = path[:pos]
        key = path[pos + 1:]

        return dict_(bucket=bucket, key=key)

    def read(self, path):

        meta = S3.parse_path(path)
        meta = self.client.get_object(Bucket=meta.bucket, Key=meta.key, RequestPayer='requester')
        data = meta['Body'].read()

        return data

    def get(self, path, dest='./'):

        print('S3 Get', path)
        meta = S3.parse_path(path)
        if dest.endswith('/'):
            dest += os.path.basename(meta.key)
        try:
            self.client.download_file(meta.bucket, meta.key, dest, {'RequestPayer': 'requester'})
        except botocore.exceptions.ClientError as ex:
            # ipython()
            if ex.response['Error']['Code'] == '404':
                raise NotFound()
            else:
                raise

    def put(self, src_file, dest_path):

        print('S3 Put', dest_path)
        meta = S3.parse_path(dest_path)
        self.client.upload_file(src_file, meta.bucket, meta.key, {'RequestPayer': 'requester'})

    def exists(self, path):

        meta = S3.parse_path(path)
        try:
            self.client.head_object(Bucket=meta.bucket, Key=meta.key, RequestPayer='requester')
            return True
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == '404':
                return False
            else:
                raise

    def list(self, dir, mask='*'):

        meta = S3.parse_path(dir)
        n, token, files = 0, None, []
        while True:
            n += 1
            params = dict(Bucket=meta.bucket, Prefix=meta.key, Delimiter='/',
                          RequestPayer='requester')
            if token:
                res = self.client.list_objects_v2(ContinuationToken=token, **params)
            else:
                res = self.client.list_objects_v2(**params)
            mask = mask.replace('?', '.').replace('*', '.+?')
            for file in res.get('CommonPrefixes', []):
                if mask != '*' and re.match(meta.key + mask, file['Prefix']):
                    files.append(file['Prefix'])
            for file in res.get('Contents', []):
                if mask != '*' and re.match(meta.key + mask, file['Key']):
                    files.append(file['Key'])
            if not res['IsTruncated']:
                break
            token = res['NextContinuationToken']
            print(n)

        return files
