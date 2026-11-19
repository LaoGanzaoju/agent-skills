# -*- coding: utf-8 -*-
"""迁移包解压工具：list / extract
- 中文文件名安全（自动处理 cp437 回退）
- 过滤 __MACOSX/ 与 .DS_Store
- extract 模式遵守红线：目标已存在同名文件 → 跳过并记为 CONFLICT，绝不覆盖
"""
import sys, os, zipfile, json, io

sys.stdout.reconfigure(encoding='utf-8')

ZIP = sys.argv[1]
MODE = sys.argv[2]
DEST = sys.argv[3] if len(sys.argv) > 3 else None


def real_name(info):
    name = info.filename
    if not (info.flag_bits & 0x800):
        try:
            name = name.encode('cp437').decode('utf-8')
        except Exception:
            pass
    return name


def skip(name):
    parts = name.split('/')
    if any(p == '__MACOSX' for p in parts):
        return True
    if parts[-1] in ('.DS_Store', '', 'Thumbs.db'):
        return parts[-1] in ('.DS_Store', 'Thumbs.db')
    return False


zf = zipfile.ZipFile(ZIP)
entries = []
for info in zf.infolist():
    name = real_name(info)
    if skip(name):
        continue
    entries.append((info, name))

if MODE == 'list':
    out = []
    for info, name in entries:
        out.append({'name': name, 'dir': name.endswith('/'), 'size': info.file_size})
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0)

# extract
written, conflicts, dirs = [], [], []
for info, name in entries:
    target = os.path.join(DEST, *name.split('/'))
    if name.endswith('/'):
        os.makedirs(target, exist_ok=True)
        dirs.append(name)
        continue
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.exists(target):
        conflicts.append(name)
        continue
    with zf.open(info) as src, open(target, 'wb') as dst:
        dst.write(src.read())
    written.append({'name': name, 'size': info.file_size})

print(json.dumps({'written': written, 'conflicts': conflicts, 'dirs_created': dirs},
                 ensure_ascii=False, indent=1))
