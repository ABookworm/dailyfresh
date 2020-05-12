from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from django.conf import settings


class FDFSStorage(Storage):
    """fdfs dfs文件存储类"""
    def __init__(self, base_url=None, client_conf=None):
        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

    def _open(self, name, mode='rb'):
        pass

    def _save(self, name, content):
        """保存文件"""
        # 创建一个客户端对象
        client = Fdfs_client(self.client_conf)
        ret = client.upload_by_buffer(content.read())
        # @return dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }

        if ret.get('Status') != 'Upload successed.':
            raise Exception('upload file failed')
        filename = ret.get('Remote file_id')
        return filename

    def exists(self, name):
        """django 判断文件是否可用"""
        return False

    def url(self, name):
        return self.base_url+name