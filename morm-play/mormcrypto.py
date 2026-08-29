"""Ed25519 verify (RFC 8032, pure-python, verify-only) + m0r address derivation.

stdlib のみ。Mac Mini system python3.9 で動く。投稿/コメントのシビル耐性の根。
アドレス方式は既存ウォレット(morm-l1/crypto.py・account.html)と一致:
  m0r + base32(BLAKE2b-256(ed25519_pubkey)[-20:]).lower()  (35字)
"""
import base64
import hashlib

_q = 2 ** 255 - 19


def _inv(x):
    return pow(x, _q - 2, _q)


_d = (-121665 * _inv(121666)) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y):
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = (4 * _inv(5)) % _q
_Bx = _xrecover(_By)
_B = (_Bx % _q, _By % _q)


def _edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _d * x1 * x2 * y1 * y2)
    return (x3 % _q, y3 % _q)


def _scalarmult(P, e):
    if e == 0:
        return (0, 1)
    Q = _scalarmult(P, e // 2)
    Q = _edwards(Q, Q)
    if e & 1:
        Q = _edwards(Q, P)
    return Q


def _bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1


def _Hint(m):
    h = hashlib.sha512(m).digest()
    return sum(2 ** i * _bit(h, i) for i in range(512))


def _isoncurve(P):
    x, y = P
    return (-x * x + y * y - 1 - _d * x * x * y * y) % _q == 0


def _decodepoint(s):
    y = sum(2 ** i * _bit(s, i) for i in range(255))
    x = _xrecover(y)
    if x & 1 != _bit(s, 255):
        x = _q - x
    P = (x, y)
    if not _isoncurve(P):
        raise ValueError("not on curve")
    return P


def ed25519_verify(pub32: bytes, msg: bytes, sig64: bytes) -> bool:
    try:
        if len(sig64) != 64 or len(pub32) != 32:
            return False
        R = _decodepoint(sig64[:32])
        A = _decodepoint(pub32)
        S = sum(2 ** i * _bit(sig64[32:], i) for i in range(256))
        h = _Hint(sig64[:32] + pub32 + msg)
        v1 = _scalarmult(_B, S)
        v2 = _edwards(R, _scalarmult(A, h))
        return v1 == v2
    except Exception:
        return False


def m0r_address(pub32: bytes) -> str:
    h = hashlib.blake2b(pub32, digest_size=32).digest()
    return "m0r" + base64.b32encode(h[-20:]).decode().lower()


# --- Ed25519 sign (RFC 8032・トレジャリー署名用) ---
_L = 2 ** 252 + 27742317777372353535851937790883648493


def _encodeint(y):
    return bytes((y >> (8 * i)) & 0xFF for i in range(32))


def _encodepoint(P):
    x, y = P
    e = bytearray(_encodeint(y))
    e[31] |= (x & 1) << 7
    return bytes(e)


def _secret_scalar(seed):
    h = hashlib.sha512(seed).digest()
    a = 2 ** 254 + sum(2 ** i * _bit(h, i) for i in range(3, 254))
    return a, h


def ed25519_pubkey(seed32: bytes) -> bytes:
    a, _ = _secret_scalar(seed32)
    return _encodepoint(_scalarmult(_B, a))


def ed25519_sign(seed32: bytes, msg: bytes) -> bytes:
    a, h = _secret_scalar(seed32)
    A = _encodepoint(_scalarmult(_B, a))
    r = _Hint(h[32:64] + msg)
    R = _scalarmult(_B, r)
    S = (r + _Hint(_encodepoint(R) + A + msg) * a) % _L
    return _encodepoint(R) + _encodeint(S)


if __name__ == "__main__":
    # RFC 8032 test vector 1 (empty message)
    pub = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sig = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    assert ed25519_verify(pub, b"", sig), "RFC8032 vector1 FAIL"
    assert not ed25519_verify(pub, b"x", sig), "should reject wrong msg"
    assert m0r_address(bytes(32)) == "m0rg2mtdtqksspmv6s4h6j7qeqygnsg4fod", "m0r parity FAIL"
    # RFC 8032 sign vector 1
    seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    assert ed25519_pubkey(seed).hex() == "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "pubkey FAIL"
    assert ed25519_sign(seed, b"").hex() == (
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"), "sign FAIL"
    assert ed25519_verify(ed25519_pubkey(seed), b"hello", ed25519_sign(seed, b"hello")), "sign/verify roundtrip FAIL"
    print("mormcrypto self-test: OK (verify + sign + m0r)")
