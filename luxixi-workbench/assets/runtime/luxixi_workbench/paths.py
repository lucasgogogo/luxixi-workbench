import json
import os
import stat
from pathlib import Path
from platformdirs import user_data_path
from . import APP_ID

MARKER = '.luxixi-workbench.json'

def linked(path):
    try:
        return path.is_symlink() or (os.name=='nt' and bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT))
    except FileNotFoundError:
        return False

def data_path(value=None):
    path = Path(value).expanduser() if value else user_data_path('LuxixiWorkbench', appauthor=False) / 'main'
    return path.resolve()

def atomic_json(path, payload):
    temp = path.with_name(path.name + '.' + os.urandom(6).hex() + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(payload, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()

def owned_root(value=None, create=False):
    raw=(Path(value).expanduser() if value else user_data_path('LuxixiWorkbench', appauthor=False)/'main').absolute()
    if any(linked(p) for p in [raw,*raw.parents]):
        raise ValueError('数据目录及祖先目录不能是链接/junction')
    root = data_path(value)
    marker = root / MARKER
    if linked(marker) or (root.exists() and not root.is_dir()):
        raise ValueError('数据目录或身份标记不安全')
    if not marker.exists():
        if not create:
            raise ValueError('该目录不是本工作台的数据目录')
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if any(root.iterdir()):
            raise ValueError('拒绝使用非空且没有本应用标记的目录')
        with marker.open('x', encoding='utf-8') as file:
            json.dump({'app': APP_ID, 'schema': 1}, file)
    identity = json.loads(marker.read_text(encoding='utf-8'))
    if identity != {'app': APP_ID, 'schema': 1}:
        raise ValueError('数据目录身份/版本不匹配')
    for name in ['workbench.sqlite3', 'runtime.json', 'service.lock', 'service.log', 'service-config.json']:
        if linked(root / name):
            raise ValueError('不允许数据文件符号链接')
    return root

def service_port(root, explicit=None):
    config=root/'service-config.json'
    saved=None
    if config.exists():
        value=json.loads(config.read_text(encoding='utf-8'))
        if (not isinstance(value,dict) or set(value)!={'app','schema','port'}
                or value['app']!=APP_ID or value['schema']!=1
                or type(value['port']) is not int or not 1024<=value['port']<=65535):
            raise ValueError('服务入口配置无效；保留原配置，请核对后恢复')
        saved=value['port']
    port=explicit if explicit is not None else (saved or 8876)
    if type(port) is not int or not 1024<=port<=65535:
        raise ValueError('端口必须在1024至65535之间')
    return port

class InstanceLock:
    def __init__(self, root):
        self.file = (root / 'service.lock').open('a+b')

    def acquire(self):
        self.file.seek(0)
        if os.name == 'nt':
            import msvcrt
            if self.file.read(1) == b'':
                self.file.write(b'0')
                self.file.flush()
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def close(self):
        self.file.close()
