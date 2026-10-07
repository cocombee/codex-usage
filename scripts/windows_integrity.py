"""Windows PE/ASAR integrity. Never disables a fuse or writes a Store package."""
import hashlib
import json
import mmap
from pathlib import Path
import struct

from integrity import archive_header, require

FUSE_SENTINEL = b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'


class PE:
    """Bounded reader for PE32+ resource data, without loading executable code."""
    def __init__(self, data):
        self.data = data
        require(len(data) >= 64 and data[:2] == b'MZ', 'Expected DOS/PE header')
        pe = self.u32(60)
        require(self.read(pe, 4) == b'PE\0\0', 'Invalid PE signature')
        require(self.u16(pe + 4) == 0x8664, 'Only the inspected Windows x64 build is supported')
        count, size = self.u16(pe + 6), self.u16(pe + 20)
        optional = pe + 24
        require(size >= 152 and self.u16(optional) == 0x20b, 'Expected PE32+ optional header')
        require(self.u32(optional + 108) >= 5, 'Missing PE data directories')
        self.checksum = optional + 64
        self.security = optional + 112 + 4 * 8
        self.certificate = (self.u32(self.security), self.u32(self.security + 4))
        self.sections = []
        for index in range(count):
            at = optional + size + index * 40
            raw = self.read(at, 40)
            virtual_size, rva, raw_size, offset = struct.unpack_from('<IIII', raw, 8)
            self.read(offset, raw_size)
            self.sections.append((rva, virtual_size, offset, raw_size))
        rva, length = self.u32(optional + 128), self.u32(optional + 132)
        require(rva and length >= 16, 'Missing PE resource directory')
        self.resource = self.rva_offset(rva, length)
        self.resource_size = length

    def read(self, offset, size):
        require(offset >= 0 and size >= 0 and offset + size <= len(self.data), 'PE read outside file')
        return self.data[offset:offset + size]

    def u16(self, at):
        return struct.unpack('<H', self.read(at, 2))[0]

    def u32(self, at):
        return struct.unpack('<I', self.read(at, 4))[0]

    def rva_offset(self, rva, size):
        matches = [offset + rva - start for start, _, offset, length in self.sections
                   if start <= rva and rva + size <= start + length]
        require(len(matches) == 1, 'Ambiguous or out-of-bounds PE RVA')
        return matches[0]

    def resource_offset(self, relative, length):
        require(0 <= relative and relative + length <= self.resource_size, 'Resource outside PE directory')
        return self.resource + relative

    def resource_entries(self):
        result, visited = [], set()

        def visit(relative, names):
            require(relative not in visited and len(names) < 3, 'Cyclic or excessively deep PE resources')
            visited.add(relative)
            at = self.resource_offset(relative, 16)
            count = self.u16(at + 12) + self.u16(at + 14)
            self.resource_offset(relative + 16, count * 8)
            for index in range(count):
                entry = at + 16 + index * 8
                name, child = self.u32(entry), self.u32(entry + 4)
                if name & 0x80000000:
                    text_at = self.resource_offset(name & 0x7fffffff, 2)
                    length = self.u16(text_at) * 2
                    self.resource_offset((name & 0x7fffffff) + 2, length)
                    name = self.read(text_at + 2, length).decode('utf-16le')
                path = (*names, name)
                if child & 0x80000000:
                    visit(child & 0x7fffffff, path)
                else:
                    require(len(path) == 3, 'Unexpected PE resource depth')
                    node = self.resource_offset(child, 16)
                    size = self.u32(node + 4)
                    offset = self.rva_offset(self.u32(node), size)
                    result.append((path, offset, size))
        visit(0, ())
        return result


def inspect_launcher(data):
    pe = PE(data)
    matches = [(path, at, size) for path, at, size in pe.resource_entries()
               if str(path[0]).lower() == 'integrity' and str(path[1]).lower() == 'electronasar']
    require(len(matches) == 1, 'Expected exactly one Integrity/ElectronAsar PE resource')
    _, at, size = matches[0]
    raw = pe.read(at, size)
    text = raw.decode('utf-8')
    value, end = json.JSONDecoder().raw_decode(text)
    require(len(value) == 1 and isinstance(value[0], dict), 'Unsupported ASAR integrity resource')
    entry = value[0]
    require(set(entry) == {'file', 'alg', 'value'} and entry['file'] == 'resources\\app.asar'
            and entry['alg'] == 'SHA256', 'Unexpected ASAR integrity resource entry')
    digest = entry['value']
    require(isinstance(digest, str) and len(digest) == 64
            and all(c in '0123456789abcdef' for c in digest), 'Invalid ASAR resource digest')
    require(raw[:end].count(digest.encode()) == 1, 'Ambiguous ASAR resource digest')
    return {'sha256': digest, 'digest_offset': at + raw.index(digest.encode()),
            'resource_offset': at, 'resource_size': size, 'certificate': pe.certificate,
            'security_offset': pe.security, 'checksum_offset': pe.checksum}


def inspect_fuses(path):
    with Path(path).open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        at = data.find(FUSE_SENTINEL)
        require(at >= 0 and data.find(FUSE_SENTINEL, at + 1) < 0, 'Missing or ambiguous fuse wire')
        start = at + len(FUSE_SENTINEL)
        require(start + 2 <= len(data), 'Truncated fuse header')
        version, length = data[start:start + 2]
        require(version == 1 and length >= 6 and start + 2 + length <= len(data), 'Invalid fuse wire')
        wire = data[start + 2:start + 2 + length].decode('ascii')
        require(wire[4:6] == '11', 'ASAR validation and only-ASAR loading must remain enabled')
        return {'version': version, 'wire': wire}


def rewrite_launcher(data, before_hash, after_hash):
    """Return an honestly unsigned local launcher with a synchronized ASAR hash.

    The input must already have passed pinned hashes and Authenticode verification.
    Other native binaries and their valid vendor signatures remain untouched.
    """
    info = inspect_launcher(data)
    require(info['sha256'] == before_hash, 'Original launcher/header mismatch')
    require(len(after_hash) == 64 and all(c in '0123456789abcdef' for c in after_hash), 'Invalid new header hash')
    result = bytearray(data)
    offset, size = info['certificate']
    require(offset > 0 and size >= 8 and offset + size == len(data), 'Unsupported Authenticode certificate layout')
    require(offset >= max(pos + length for _, _, pos, length in PE(data).sections), 'Certificate overlaps PE sections')
    digest_at = info['digest_offset']
    result[digest_at:digest_at + 64] = after_hash.encode()
    # A changed launcher is no longer OpenAI-signed. Remove the stale signature,
    # without installing a certificate or changing Windows trust policy.
    result[info['security_offset']:info['security_offset'] + 8] = b'\0' * 8
    result[info['checksum_offset']:info['checksum_offset'] + 4] = b'\0' * 4
    del result[offset:]
    require(inspect_launcher(result)['sha256'] == after_hash, 'Launcher hash readback failed')
    return bytes(result)


def verify_pair(app):
    app = Path(app)
    header = archive_header(app / 'resources/app.asar')['sha256']
    launcher = inspect_launcher((app / 'ChatGPT.exe').read_bytes())
    require(launcher['sha256'] == header, 'Native launcher rejects this ASAR header')
    return {'header_sha256': header, 'fuses': inspect_fuses(app / 'chrome.dll')}
