"""P1 検証シナリオ — spend-key / view-key 導出（MORMDEX-SPEC.md v0.2 §8 P1）。

実行:  python3 scenario_confidential_p1.py

確認する不変条件:
  1. 決定性        … 同じアカウント種から常に同じ鍵/アドレス/payment code
  2. spend互換     … spend種は既存アカウント種そのもの＝従来の署名/検証/社会復旧が有効
  3. 一方向性      … spend→view は導出可、view→spend は不能（HKDF）
  4. 選択的開示    … view-only ビューで受取検出はできるが *署名(spend)はできない*
  5. payment code  … m0rc… の round-trip（送金者が spend_pub/view_pub を復元）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from morm_l1 import crypto, confidential
from morm_l1.shamir import split, combine


def line(t=""):
    print(t)


def main() -> int:
    line("=" * 66)
    line("MORM 機密精算レイヤ  P1: spend/view 鍵導出 検証")
    line("=" * 66)

    # --- アカウント作成（既存 crypto.keygen: ed25519 種） ---
    account_seed, account_pub = crypto.keygen()
    ck = confidential.derive(account_seed)

    line("\n[アカウント]")
    line(f"  透明アドレス   : {ck.address}")
    line(f"  payment code   : {ck.payment_code}")
    line(f"  spend_pub      : {ck.spend_pub.hex()[:24]}…")
    line(f"  view_pub       : {ck.view_pub.hex()[:24]}…")

    ok = True

    # 1. 決定性
    ck2 = confidential.derive(account_seed)
    det = (ck2.address == ck.address and ck2.payment_code == ck.payment_code
           and ck2.view_priv == ck.view_priv)
    line(f"\n[1] 決定性導出                : {'OK' if det else 'FAIL'}")
    ok &= det

    # 2. spend互換（既存アカウント種＝spend種。従来の署名/検証が通る）
    msg = b"move 100 MORM"
    sig = crypto.sign(ck.spend_seed, msg)
    compat = (ck.spend_pub == account_pub and crypto.verify(ck.spend_pub, sig, msg))
    line(f"[2] 既存ed25519 spendと互換   : {'OK' if compat else 'FAIL'}")
    ok &= compat

    # 2b. 社会復旧(shamir)が spend種に効くことも確認（3-of-5）
    shares = split(ck.spend_seed, threshold=3, num_shares=5)
    recovered = combine(shares[:3])
    rec_ok = (recovered == ck.spend_seed)
    line(f"[2b] shamir 3-of-5 社会復旧    : {'OK' if rec_ok else 'FAIL'}")
    ok &= rec_ok

    # 3. 一方向性: view種は spend種から出るが、逆は不能
    view_again = confidential.view_priv_from_seed(ck.spend_seed)
    forward = (view_again == ck.view_priv)
    # view_priv しか知らない攻撃者は spend種(=32B ed25519)を復元できない。
    # 少なくとも view_priv から spend_pub は導けない（別カーブ・別鍵）ことを示す。
    from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
    leaked = False
    try:
        # 誤って view_priv を ed25519 種として使っても、正しい spend_pub にはならない
        wrong_pub = crypto.pubkey_from_seed(ck.view_priv)
        leaked = (wrong_pub == ck.spend_pub)
    except Exception:
        leaked = False
    oneway = forward and not leaked
    line(f"[3] 一方向 spend→view のみ     : {'OK' if oneway else 'FAIL'}")
    ok &= oneway

    # 4. 選択的開示: 本人が監査人へ view-only を渡す
    audit = ck.to_view_only()
    #   4a. 監査人は同じアドレス/payment code を確認できる（受取検出の土台）
    view_sees = (audit.address == ck.address and audit.payment_code == ck.payment_code)
    #   4b. しかし監査人は署名(spend)できない — spend_seed を持っていない
    can_spend = hasattr(audit, "spend_seed")
    disclosure = view_sees and not can_spend
    line(f"[4] view-only 開示は読取専用   : {'OK' if disclosure else 'FAIL'}")
    line(f"      - 受取検出の土台を確認   : {view_sees}")
    line(f"      - 署名権限は含まない     : {not can_spend}")
    ok &= disclosure

    # 5. payment code round-trip（送金者側の復元）
    sp, vp = confidential.decode_payment_code(ck.payment_code)
    rt = (sp == ck.spend_pub and vp == ck.view_pub)
    line(f"[5] payment code round-trip   : {'OK' if rt else 'FAIL'}")
    ok &= rt

    line("\n" + "=" * 66)
    line(f"結果: {'ALL GREEN ✅' if ok else 'FAILURE ❌'}")
    line("=" * 66)
    if ok:
        line("\n次(P2): この spend_pub/view_pub から *ステルスアドレス* を導出し、")
        line("        受取毎にワンタイム宛先を作る（送金者・第三者に紐付けさせない）。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
