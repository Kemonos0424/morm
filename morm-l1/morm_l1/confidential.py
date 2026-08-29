"""MORM 機密精算レイヤ — P1: spend-key / view-key 導出。

MORMDEX-SPEC.md v0.2 §3(鍵設計) / §8(P1) の実装。設計は先行技術に依拠する（§7）:
  * デュアルキー（spend / view）と payment code = CryptoNote / Monero
  * viewing key による選択的開示 = Zcash Sapling

方針（ノンカストディ・コンセプト優先版）:
  * **spend-key** … 既存アカウントの ed25519 種そのもの。資産を動かす署名権限。
    運営は保持しない。social recovery(shamir.py) は従来どおりこの種に効く。
  * **view-key**  … spend 種から一方向(HKDF)で導出する X25519 秘密。
    自分宛の受取検出と金額の復号(P2)に使う *読み取り専用* 鍵。
    本人が税理士・当局へ **選択的に開示** できる（渡しても spend はできない）。

セキュリティの向き（重要）:
    spend種 → view種 は導出できる（所有者は両方持つ）。
    view種 → spend種 は導出できない（HKDF は一方向）。
    ∴ view-key を渡しても資産移動権限は漏れない。Monero の決定性ウォレットで
    private view key を Hs(spend) とするのと同じ向き。

依存: `cryptography` のみ（既存依存）。新規パッケージ無し。
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import serialization

from . import crypto

# 共有コンフィデンシャル・アドレス（payment code）の prefix。
# 素の m0r（透明アカウント）と視覚的に区別する。m0rc = "MORM confidential"。
PAYCODE_PREFIX = "m0rc"

# HKDF ドメイン分離ラベル。用途ごとに info を変え、鍵の相互導出を防ぐ。
_SALT = b"MORM-confidential-v1"
_INFO_VIEW = b"MORM/confidential/view/x25519/v1"


def _hkdf(ikm: bytes, info: bytes, length: int = 32) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=length, salt=_SALT, info=info
    ).derive(ikm)


def _x25519_pub(priv32: bytes) -> bytes:
    return (
        x25519.X25519PrivateKey.from_private_bytes(priv32)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )


@dataclass(frozen=True)
class ConfidentialKeys:
    """あるアカウントの機密レイヤ鍵一式（所有者＝spend種を持つ本人）。"""

    spend_seed: bytes   # 32B ed25519 種（＝既存アカウント鍵。署名/資産移動）
    spend_pub: bytes    # 32B ed25519 公開鍵
    view_priv: bytes    # 32B X25519 秘密（受取検出・金額復号。開示可能）
    view_pub: bytes     # 32B X25519 公開鍵

    @property
    def address(self) -> str:
        """透明アカウントアドレス（m0r…）。spend 公開鍵が支配する。"""
        return crypto.address(self.spend_pub)

    @property
    def payment_code(self) -> str:
        """送金者に渡す共有アドレス（m0rc…）。spend_pub + view_pub を束ねる。"""
        return encode_payment_code(self.spend_pub, self.view_pub)

    def to_view_only(self) -> "ViewOnlyKeys":
        """本人が第三者へ渡す *読み取り専用* ビュー（spend種を含まない）。"""
        return ViewOnlyKeys(
            spend_pub=self.spend_pub, view_priv=self.view_priv, view_pub=self.view_pub
        )


@dataclass(frozen=True)
class ViewOnlyKeys:
    """選択的開示で渡す監査用ビュー。受取検出・金額復号はできるが署名は不可。"""

    spend_pub: bytes
    view_priv: bytes
    view_pub: bytes

    @property
    def address(self) -> str:
        return crypto.address(self.spend_pub)

    @property
    def payment_code(self) -> str:
        return encode_payment_code(self.spend_pub, self.view_pub)


def derive(account_seed: bytes) -> ConfidentialKeys:
    """既存アカウントの 32B ed25519 種から機密レイヤ鍵一式を決定性導出。

    spend 種＝account_seed をそのまま採用（アカウント同一性を保ち、既存の
    shamir 社会復旧・アドレスと互換）。view 秘密は spend 種から HKDF で一方向導出。
    同じ account_seed からは常に同じ鍵が出る（端末間で決定性）。
    """
    if len(account_seed) != 32:
        raise ValueError(f"account_seed must be 32 bytes, got {len(account_seed)}")
    spend_pub = crypto.pubkey_from_seed(account_seed)
    view_priv = _hkdf(account_seed, _INFO_VIEW)
    view_pub = _x25519_pub(view_priv)
    return ConfidentialKeys(
        spend_seed=account_seed,
        spend_pub=spend_pub,
        view_priv=view_priv,
        view_pub=view_pub,
    )


def view_priv_from_seed(account_seed: bytes) -> bytes:
    """view 秘密だけを取り出す（spend種を露出させたくない導線用）。"""
    if len(account_seed) != 32:
        raise ValueError(f"account_seed must be 32 bytes, got {len(account_seed)}")
    return _hkdf(account_seed, _INFO_VIEW)


def encode_payment_code(spend_pub: bytes, view_pub: bytes) -> str:
    """m0rc + base32(spend_pub || view_pub)。lowercase・パディング無し。"""
    if len(spend_pub) != 32 or len(view_pub) != 32:
        raise ValueError("spend_pub and view_pub must each be 32 bytes")
    body = base64.b32encode(spend_pub + view_pub).decode().lower().rstrip("=")
    return PAYCODE_PREFIX + body


def decode_payment_code(code: str) -> tuple[bytes, bytes]:
    """m0rc… → (spend_pub, view_pub)。送金者が受取先を組み立てるのに使う。"""
    if not isinstance(code, str) or not code.startswith(PAYCODE_PREFIX):
        raise ValueError(f"not a payment code: {code!r}")
    body = code[len(PAYCODE_PREFIX):].upper()
    pad = (-len(body)) % 8
    try:
        raw = base64.b32decode(body + "=" * pad)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"bad payment code: {e}") from None
    if len(raw) != 64:
        raise ValueError(f"payment code must decode to 64 bytes, got {len(raw)}")
    return raw[:32], raw[32:]
