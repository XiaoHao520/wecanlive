import os
import os.path
import re
import subprocess
import tempfile

from django.conf import settings


def generate_sig(username):
    """ 用独立账号模式对用户名签名并返回 sig 签名串
    https://www.qcloud.com/document/product/269/1510
    https://github.com/zhaoyang21cn/SuiXinBoPHPServer
    :param username: 待签名的用户名
    :return: 返回签名成功生成的签名串
    """
    sig_file = tempfile.mktemp()
    dirname = os.path.dirname(os.path.abspath(__file__))
    output = subprocess.check_output(' '.join([
        os.path.join(dirname, 'bin', 'tls_licence_tools'),
        'gen',
        os.path.join(dirname, 'keys', 'private_key'),
        sig_file,
        settings.TENCENT_ILVB_APPID,
        username,
    ]), shell=True).decode().strip()
    assert output == 'generate sig ok', 'ILIVE 尝试签名错误，返回信息：{}'.format(output)
    return open(sig_file, 'r').read()


def verify_sig(username, sig):
    """ 对指定的用户验签，判断的 sig 签名是否正确
    https://www.qcloud.com/document/product/269/1510
    :param username: 用户名字符串
    :param sig: 签名字符串
    :return: 返回验签结果对象
    """
    sig_file = tempfile.mktemp()
    open(sig_file, 'w').write(sig)
    dirname = os.path.dirname(os.path.abspath(__file__))
    output = subprocess.check_output(' '.join([
        os.path.join(dirname, 'bin', 'tls_licence_tools'),
        'verify',
        os.path.join(dirname, 'keys', 'public_key'),
        sig_file,
        settings.TENCENT_ILVB_APPID,
        username,
    ]), shell=True).decode().split('\n')
    if not output[0] == 'verify sig ok':
        return dict(
            result=False,
            output='\n'.join(output)
        )
    else:
        expire, init_time = map(int, re.findall(r'^expire (\d+) init time (\d+)$', output[1])[0])
        return dict(
            result=True,
            expire=expire,
            init_time=init_time,
        )
