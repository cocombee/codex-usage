"""ASAR/native integrity validation, adapted from the verified Hermes repair.
No fuses are changed. Only this project's staged New Build may be synchronized.
"""
import hashlib
import json
import mmap
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = Path('Contents/Frameworks/Codex Framework.framework')
SENTINEL = b'AGbevlPCksUGKNL8TSn7wGmJEuJsXb2A'
FUSE_SENTINEL = b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'
SHA256 = re.compile(r'[0-9a-f]{64}\Z')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):
            digest.update(chunk)
    return digest.hexdigest()

def layout(path):
    with path.open('rb') as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        require(len(data) >= 32, 'Truncated Mach-O')
        header = struct.unpack_from('<IiiIIIII', data, 0)
        require(header[0] == 0xfeedfacf and header[1] == 0x100000c, 'Expected thin arm64 Mach-O')
        end = 32 + header[5]
        require(end <= len(data), 'Truncated load commands')
        position = 32
        result = {'slots': [], 'signatures': [], 'linkedit_size_fields': []}
        for _ in range(header[4]):
            require(position + 8 <= end, 'Truncated load command')
            cmd, size = struct.unpack_from('<II', data, position)
            require(size >= 8 and size % 8 == 0 and position + size <= end, 'Invalid load command size')
            if cmd == 0x1d:
                require(size == 16, 'Unexpected code-signature command size')
                _, _, offset, length = struct.unpack_from('<IIII', data, position)
                require(offset + length <= len(data), 'Invalid code-signature range')
                result['signatures'].append({'offset': offset, 'size': length, 'command_offset': position})
            if cmd == 0x19:
                require(size >= 72, 'Truncated segment')
                segment = struct.unpack_from('<II16sQQQQiiII', data, position)
                require(size == 72 + 80 * segment[-2], 'Invalid section table size')
                if segment[2].rstrip(b'\0') == b'__LINKEDIT':
                    result['linkedit_size_fields'].extend([position + 32, position + 48])
                for index in range(segment[-2]):
                    section = struct.unpack_from('<16s16sQQIIIIIIII', data, position + 72 + 80 * index)
                    if (section[1].rstrip(b'\0'), section[0].rstrip(b'\0')) != (b'__DATA_CONST', b'__asar_integrity'):
                        continue
                    length, offset = section[3], section[4]
                    require(offset + length <= len(data), 'Native section outside Mach-O')
                    require(segment[5] <= offset and offset + length <= segment[5] + segment[6],
                            'Native section outside segment')
                    raw = data[offset:offset + length]
                    require(raw.count(SENTINEL) == 1, 'Ambiguous or missing native integrity sentinel')
                    start = raw.index(SENTINEL) + len(SENTINEL)
                    require(start + 34 <= len(raw), 'Truncated native integrity slot')
                    result['slots'].append({'used': raw[start], 'version': raw[start + 1],
                                            'digest': raw[start + 2:start + 34].hex(),
                                            'digest_offset': offset + start + 2,
                                            'section_offset': offset, 'section_size': length})
            position += size
        require(position == end, 'Inconsistent Mach-O command count')
        require(len(result['signatures']) == 1, 'Expected one embedded code signature')
        fuse = data.find(FUSE_SENTINEL)
        if fuse >= 0:
            require(data.find(FUSE_SENTINEL, fuse + 1) == -1, 'Ambiguous fuse sentinel')
            start = fuse + len(FUSE_SENTINEL)
            version, length = data[start], data[start + 1]
            require(version == 1 and length >= 6 and start + 2 + length <= len(data), 'Invalid fuse wire')
            result['fuses'] = {'version': version, 'wire': data[start + 2:start + 2 + length].decode('ascii')}
        return result

def stable_stat(path):
    # Drive may update extended metadata/ctime without changing signed bytes.
    # Identity, size and mtime plus repeated hashes/signature checks guard content.
    value = Path(path).stat()
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns]

def stable_sha(path):
    before = stable_stat(path)
    digest = sha(path)
    require(stable_stat(path) == before, 'File changed while hashing: ' + str(path))
    return digest

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result

def archive_header(path):
    path = Path(path)
    with path.open('rb') as stream:
        prefix = stream.read(16)
        require(len(prefix) == 16, 'Truncated ASAR prefix')
        size_pickle, header_size, payload_size, json_size = struct.unpack('<IIII', prefix)
        require(size_pickle == 4 and payload_size + 4 == header_size, 'Invalid ASAR pickle sizes')
        require(0 < json_size <= payload_size - 4 and header_size <= 64 * 1024 * 1024,
                'Invalid ASAR JSON size')
        require(8 + header_size <= path.stat().st_size, 'ASAR data offset beyond archive')
        raw = stream.read(json_size)
        require(len(raw) == json_size, 'Truncated ASAR JSON')
        tree = json.loads(raw, object_pairs_hook=unique_object)
        require(isinstance(tree, dict) and isinstance(tree.get('files'), dict), 'Invalid ASAR file tree')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'data_offset': 8 + header_size,
            'tree': tree}

def archive_entries(path):
    header = archive_header(path)
    result = {}

    def visit(node, prefix=''):
        for name, entry in node['files'].items():
            require(name not in ('', '.', '..') and '/' not in name and '\\' not in name,
                    'Unsafe ASAR entry name')
            require(isinstance(entry, dict), 'Invalid ASAR entry')
            relative = prefix + name
            if 'files' in entry:
                visit(entry, relative + '/')
            else:
                result[relative] = entry
    visit(header['tree'])
    return header, result

def entry_identity(entry):
    if entry is None:
        return None
    if 'link' in entry:
        return {'link': entry['link']}
    return {'size': entry.get('size'), 'unpacked': bool(entry.get('unpacked', False)),
            'hash': entry.get('integrity', {}).get('hash')}

def changed_entries(before_archive, after_archive):
    _, before = archive_entries(before_archive)
    _, after = archive_entries(after_archive)
    return sorted(name for name in set(before) | set(after)
                  if entry_identity(before.get(name)) != entry_identity(after.get(name)))

def verify_entries(path, names):
    path = Path(path)
    header, entries = archive_entries(path)
    require(len(names) == len(set(names)), 'Duplicate requested ASAR entry')
    results = []
    with path.open('rb') as stream:
        for name in names:
            require(name in entries, 'Missing ASAR entry: ' + name)
            entry = entries[name]
            require('offset' in entry and not entry.get('unpacked') and 'link' not in entry,
                    'Expected a packed ASAR entry: ' + name)
            size, offset = entry['size'], int(entry['offset'])
            require(type(size) is int and size >= 0 and offset >= 0, 'Invalid entry range')
            require(header['data_offset'] + offset + size <= path.stat().st_size,
                    'Entry outside ASAR')
            stream.seek(header['data_offset'] + offset)
            data = stream.read(size)
            require(len(data) == size, 'Truncated packed entry')
            integrity = entry['integrity']
            require(integrity['algorithm'] == 'SHA256' and SHA256.fullmatch(integrity['hash']),
                    'Unsupported entry hash')
            actual = hashlib.sha256(data).hexdigest()
            require(actual == integrity['hash'], 'Entry full hash mismatch: ' + name)
            block = integrity['blockSize']
            require(type(block) is int and block > 0, 'Invalid block size')
            blocks = [hashlib.sha256(data[index:index + block]).hexdigest()
                      for index in range(0, len(data), block)]
            require(blocks == integrity['blocks'], 'Entry block hash mismatch: ' + name)
            results.append({'path': name, 'sha256': actual, 'size': size,
                            'block_count': len(blocks), 'full_and_block_hashes_valid': True})
    return results

def binary_path(app):
    app = Path(app).resolve(strict=True)
    path = (app / FRAMEWORK / 'Versions/Current/Codex Framework').resolve(strict=True)
    require(path.is_relative_to(app) and path.is_file(), 'Framework binary escaped bundle')
    return path

def inspect(app):
    app = Path(app).resolve(strict=True)
    info_path = app / 'Contents/Info.plist'
    native = binary_path(app)
    observed = {info_path: stable_stat(info_path), native: stable_stat(native)}
    info = plistlib.loads(info_path.read_bytes())
    dictionary = info.get('ElectronAsarIntegrity')
    require(isinstance(dictionary, dict) and dictionary, 'Missing ASAR integrity dictionary')
    digest = hashlib.sha256()
    archives = []
    for relative in sorted(dictionary):
        require(isinstance(relative, str) and '\\' not in relative, 'Unsafe integrity dictionary path')
        parts = PurePosixPath(relative)
        require(not parts.is_absolute() and parts.parts and parts.parts[0] == 'Resources'
                and str(parts) == relative and all(part not in ('.', '..') for part in parts.parts)
                and parts.suffix == '.asar', 'Unsafe integrity dictionary path')
        entry = dictionary[relative]
        require(isinstance(entry, dict) and set(entry) == {'algorithm', 'hash'}, 'Invalid integrity dictionary entry')
        require(entry['algorithm'] == 'SHA256' and isinstance(entry['hash'], str)
                and SHA256.fullmatch(entry['hash']), 'Unsupported or malformed dictionary hash')
        archive = (app / 'Contents' / relative).resolve(strict=True)
        require(archive.is_relative_to(app), 'Dictionary archive escaped bundle')
        observed[archive] = stable_stat(archive)
        header = archive_header(archive)
        require(header['sha256'] == entry['hash'], 'Dictionary/header mismatch: ' + relative)
        for value in (relative, entry['algorithm'], entry['hash']):
            digest.update(value.encode('utf-8'))
        archives.append({'path': relative, 'sha256': stable_sha(archive), 'header_sha256': header['sha256']})
    details = layout(native)
    require(len(details['slots']) == 1, 'Expected exactly one native integrity slot')
    slot = details['slots'][0]
    require((slot['used'], slot['version']) == (1, 1), 'Native integrity must stay enabled/version 1')
    fuses = details.get('fuses', {})
    require(fuses.get('version') == 1 and fuses.get('wire', '')[4:6] == '11',
            'Integrity and only-ASAR fuses must stay enabled')
    critical = {'info_sha256': stable_sha(info_path), 'native_sha256': stable_sha(native),
                'archives': archives}
    require(all(stable_stat(path) == prior for path, prior in observed.items()),
            'Bundle changed during integrity inspection')
    fingerprint = hashlib.sha256(json.dumps(critical, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'bundle': str(app), 'version': info.get('CFBundleShortVersionString'),
            'framework_binary': str(native.relative_to(app)), 'native_slot': slot, 'fuses': fuses,
            'dictionary_digest': digest.hexdigest(), 'native_matches_dictionary': slot['digest'] == digest.hexdigest(),
            'critical': critical, 'fingerprint': fingerprint}

def guard(app, expected_fingerprint=None):
    state = inspect(app)
    require(state['native_matches_dictionary'], 'Enabled native ASAR slot rejects the current dictionary')
    require(expected_fingerprint is None or state['fingerprint'] == expected_fingerprint,
            'Staged bundle changed since its verified receipt')
    result = subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(Path(app))],
                            capture_output=True, text=True, timeout=90)
    require(result.returncode == 0, 'Deep-strict signature verification failed: ' + result.stderr)
    require(inspect(app)['fingerprint'] == state['fingerprint'], 'Bundle changed while verifying signature')
    return dict(state, deep_strict_signature_valid=True)

def patch_digest(app):
    """Digest-only primitive; caller must perform visible signing before installation."""
    app = Path(app).resolve(strict=True)
    require(app == (ROOT / 'New Build' / 'ChatGPT.app').resolve(), 'Only canonical staged bundles may be synchronized')
    before = inspect(app)
    if before['native_matches_dictionary']:
        return {'status': 'already_synchronized', 'before': before, 'after': before}
    path = binary_path(app)
    offset = before['native_slot']['digest_offset']
    with path.open('r+b') as stream:
        stream.seek(offset)
        require(stream.read(32).hex() == before['native_slot']['digest'], 'Native slot changed before write')
        stream.seek(offset)
        require(stream.write(bytes.fromhex(before['dictionary_digest'])) == 32, 'Short native digest write')
        stream.flush()
        os.fsync(stream.fileno())
    after = inspect(app)
    require(after['native_matches_dictionary'], 'Native digest readback failed')
    require(before['critical']['archives'] == after['critical']['archives']
            and before['critical']['info_sha256'] == after['critical']['info_sha256']
            and before['fuses'] == after['fuses'], 'Archive, dictionary or fuses changed')
    return {'status': 'synchronized', 'before': before, 'after': after}
