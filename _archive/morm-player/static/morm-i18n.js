// MORM i18n — minimal dictionary lookup with EN / JA strings.
//
// Design: every UI string lives in DICT under a namespaced key
// (`wallet.title`, `upload.action.live` etc.), and pages either:
//   (a) tag DOM nodes with `data-i18n="<key>"` and call `applyDom()`
//       once on load (and again whenever the language changes), or
//   (b) call `t(<key>, params?)` directly from JS for dialog text /
//       state-machine labels that are rebuilt every render.
//
// `setLang(lang)` persists to localStorage and re-applies `data-i18n`.
// `currentLang()` resolves the active language: localStorage override
// first, else `navigator.language` heuristic (`ja*` → ja, else en).

const DICT = {
  en: {
    // ----- common -------------------------------------------------
    'common.cancel':           'Cancel',
    'common.dismiss':          'Dismiss',
    'common.refresh':          '↻ refresh',
    'common.edit':             'edit',
    'common.save':             'save',
    'common.signing_as':       'signing as: {addr}',
    'common.lang.en':          'EN',
    'common.lang.ja':          '日本語',
    'common.lang.label':       'Language',
    'common.identity_unset':   '— (sign in via /auth-morm)',

    // ----- 27f tx confirm dialog (morm-identity.js) ---------------
    'confirm.title':           '🔐 Confirm Transaction',
    'confirm.button':          'Confirm & Sign',
    'confirm.cancelled':       'Transaction cancelled by user',

    // ----- 27g over-cap extra ceremony ----------------------------
    'cap.title':               '⚠ Daily spending cap exceeded',
    'cap.app':                 'App: {app}',
    'cap.kind':                'Tx kind: {kind}',
    'cap.this_amount':         'This tx amount: {amount} MORM',
    'cap.spent24h':            'Already spent in last 24h: {spent} MORM',
    'cap.after':               'After this tx: {after} MORM',
    'cap.daily_cap':           'Daily cap: {cap} MORM',
    'cap.warn':                'A hostile site or compromised page may be attempting to drain the wallet. Approve only if YOU initiated this transfer.',
    'cap.ack':                 'I understand this exceeds my daily cap and I want to proceed anyway.',
    'cap.approve':             'Approve',

    // ----- 27h kind blocked ---------------------------------------
    'block.title':             '🚫 Tx kind not allowed for this page',
    'block.app':               'App: {app}',
    'block.blocked_kind':      'Blocked: {kind}',
    'block.allowed':           'Allowed for this app: {kinds}',
    'block.allowed_none':      '(none)',
    'block.note':              "This tx kind is outside this page's authorisation. Visit /wallet to review or broaden the policy.",

    // ----- /wallet page -------------------------------------------
    'wallet.pill':             'wallet',
    'wallet.identity':         'Identity',
    'wallet.address':          'Address',
    'wallet.balance':          'Balance',
    'wallet.nonce':            'Nonce',
    'wallet.policy_section':   'Per-app policy',
    'wallet.policy_hint':      'Each MORM page is allowed only certain transaction kinds and a 24-hour MORM spend cap. A hostile script on a page can’t silently broaden these — see SECURITY-DESIGN §3.4 (Phase 27g/h). Edit per row to tighten or loosen.',
    'wallet.col.app':          'App',
    'wallet.col.kinds':        'Allowed kinds',
    'wallet.col.cap':          'Spent / Cap (24h)',
    'wallet.no_spend':         'no spend',
    'wallet.fallback':         'fallback',
    'wallet.editor.cap':       'Daily cap (MORM, 0 = no spend allowed)',
    'wallet.editor.kinds':     'Allowed transaction kinds',
    'wallet.revoke_section':   'Revoke all',
    'wallet.revoke_hint':      'Wipes every per-app policy and resets the 24-hour spend counter. The next transaction from any page will trigger a fresh policy prompt as if no app had ever been authorised. Use this if you suspect a compromised script or after testing a page you no longer trust.',
    'wallet.revoke_btn':       '🚨 Revoke all (1-tap)',
    'wallet.revoke_confirm':   'Revoke ALL per-app policies and clear the 24h spend counter?\n\nNext tx from any page will require a fresh policy grant.',
    'wallet.revoke_done':      '✓ revoked at {time}',
    'wallet.balance_unreach':  '— (RPC unreachable)',
    'wallet.no_identity':      '— (no identity)',
    'wallet.loading':          'loading…',

    // ----- /upload page (camera) ----------------------------------
    'upload.pill':             'portrait upload',
    'upload.empty':            'tap "Start camera" to begin',
    'upload.action.idle':      'Start camera',
    'upload.action.live':      'Record',
    'upload.action.recording': 'Stop',
    'upload.action.captured':  'Upload & Encode',
    'upload.action.uploading': 'Uploading…',
    'upload.action.done':      'Record another',
    'upload.flip':             'Flip camera',
    'upload.discard':          'Discard clip',
    'upload.feed':             '▶ Feed',
    'upload.drop':             'or drop / pick a file',
    'upload.hud.job':          'Job',
    'upload.hud.state':        'State',
    'upload.hud.bytes':        'Bytes',
    'upload.hud.elapsed':      'Elapsed',
    'upload.hud.files':        'Files out',
    'upload.hud.content':      'Content',
    'upload.log.captured':     'captured {size} ({sec}s, {mime})',
    'upload.log.uploaded':     'upload finished in {sec}s, job_id={id}',
    'upload.log.upload_fail':  'upload failed: {err}',
    'upload.log.poll_fail':    'poll error: {err}',
    'upload.log.done':         '✓ done — open feed',
    'upload.log.err':          '✗ error: {err}',
    'upload.cam_err':          'camera error: {err}',
    'upload.unsupported':      'MediaRecorder not supported in this browser',
    'upload.feed_link':        '▶ Play {cid}…',

    // ----- /player-hls (feed) -------------------------------------
    'player.pill':             'portrait feed',
    'player.empty.loading':    'loading…',
    'player.empty.none':       '(no HLS content — run morm-core hls-encode)',
    'player.empty.error':      'error: {err}',

    // ----- /swap (Phase 28a EVM ↔ MORM bridge) --------------------
    'swap.pill':               'bridge',
    'swap.tab.lock':           '⟶ Lock (ETH → MORM)',
    'swap.tab.burn':           '⟵ Burn (MORM → ETH)',
    'swap.lock.title':         'Lock ETH on Ethereum',
    'swap.lock.desc':          'Sends a transaction to MORMBridge.lock(bytes20) on the EVM. Once mined, the relayer mints the same µMORM amount on MORM Chain L1 to your m0r… address.',
    'swap.lock.connect':       'Connect MetaMask',
    'swap.lock.connected':     'Connected: {addr}',
    'swap.lock.no_metamask':   'MetaMask not detected. Install it, or use the manual cast command shown below.',
    'swap.lock.amount':        'Amount (ETH)',
    'swap.lock.recipient':     'MORM recipient (m0r… or your identity)',
    'swap.lock.use_mine':      'use mine',
    'swap.lock.btn':           'Lock ETH',
    'swap.lock.btn_busy':      'Sending…',
    'swap.lock.tx_sent':       'EVM tx sent: {hash}',
    'swap.lock.tx_mined':      '✓ EVM tx mined in block {block}',
    'swap.lock.tx_failed':     '✗ EVM tx failed: {err}',
    'swap.lock.minted':        '✓ Relayer minted {amount} µMORM to {addr} (L1 balance updated)',
    'swap.lock.waiting_mint':  'Waiting for relayer to mint on MORM L1…',
    'swap.lock.fallback_hint': 'No MetaMask? Run this from a terminal:',
    'swap.burn.title':         'Burn MORM → release ETH',
    'swap.burn.desc':          'Signs a BRIDGE_BURN transaction with your passkey. The relayer observes it on the MORM Chain L1 and calls MORMBridge.unlock() on the EVM, releasing locked ETH to your chosen recipient.',
    'swap.burn.amount':        'Amount (µMORM)',
    'swap.burn.recipient':     'EVM recipient (0x…40 hex)',
    'swap.burn.btn':           'Burn & request unlock',
    'swap.burn.btn_busy':      'Signing…',
    'swap.burn.signed':        '✓ MORM L1 burn submitted: {hash}',
    'swap.burn.unlocked':      '✓ Relayer unlocked {amount} wei to {addr}',
    'swap.burn.cancelled':     'Burn cancelled by user',
    'swap.burn.no_identity':   'No MORM identity — sign in via /auth-morm first',
    'swap.burn.failed':        '✗ Burn failed: {err}',
    'swap.burn.waiting_unlock':'Waiting for relayer to call unlock() on EVM…',
    'swap.status.title':       'Bridge status',
    'swap.status.contract':    'Contract',
    'swap.status.locked_eth':  'ETH locked',
    'swap.status.lock_nonce':  'Lock nonce',
    'swap.status.unlock_nonce':'Unlock nonce',
    'swap.status.pending_burns':'Pending burns (L1)',
    'swap.status.evm_chain':   'EVM chain',
    'swap.status.morm_rpc':    'MORM RPC',
    'swap.status.disabled':    'Bridge is not configured on this gateway. Restart with --bridge-addr <0x…>.',

    // ----- /swap USDC tab (Phase 28b) -----------------------------
    'swap.tab.usdc':           'USDC',
    'swap.usdc.title':         'USDC bridge (ERC-20)',
    'swap.usdc.desc':          'Bridge USDC between Ethereum (ERC-20) and MORM Chain L1 (USDC.morm token-balance, mirrored 1:1). Lock USDC needs an extra approve() step before lockToken(). Burn signs a passkey BRIDGE_BURN with token=USDC.',
    'swap.usdc.sub.lock':      '⟶ Lock USDC',
    'swap.usdc.sub.burn':      '⟵ Burn USDC',
    'swap.usdc.your_balance':  'Your USDC',
    'swap.usdc.allowance':     'Bridge allowance',
    'swap.usdc.l1_balance':    'Your USDC.morm',
    'swap.usdc.faucet':        '🪙 mint 1000 USDC (test)',
    'swap.usdc.faucet_done':   '✓ minted 1000 USDC to {addr}',
    'swap.usdc.amount':        'Amount (USDC)',
    'swap.usdc.approve_btn':   '1. Approve bridge to spend USDC',
    'swap.usdc.approve_busy':  'Approving…',
    'swap.usdc.approve_done':  '✓ approve confirmed: bridge can pull {amount} USDC',
    'swap.usdc.lock_btn':      '2. Lock USDC',
    'swap.usdc.lock_busy':     'Locking…',
    'swap.usdc.locked':        '✓ Relayer minted {amount} USDC.morm to {addr}',
    'swap.usdc.burn_btn':      'Burn USDC.morm & release USDC',
    'swap.usdc.burn_busy':     'Signing…',
    'swap.usdc.unlocked':      '✓ Relayer transferred {amount} USDC to {addr}',
    'swap.usdc.need_approve':  'Approve first — current allowance {allow} < amount {amount}',
    'swap.status.usdc_token':  'USDC token',
    'swap.status.usdc_bridge': 'USDC bridge',
    'swap.status.usdc_locked': 'USDC locked',

    // /swap onboarding steps
    'guide.swap.0.title':      'Welcome to MORM Bridge',
    'guide.swap.0.body':       'This page swaps between ETH on Ethereum and µMORM on MORM Chain L1, using a federated lock/unlock bridge (MORM.md §1, §4). The "Lock" side mints; the "Burn" side releases.',
    'guide.swap.1.title':      'Lock ETH (needs MetaMask)',
    'guide.swap.1.body':       'Connect MetaMask, enter an ETH amount and a MORM recipient address (your own m0r… by default). Submit — MetaMask signs an on-chain MORMBridge.lock(). The relayer mints µMORM to your MORM L1 address within a few seconds.',
    'guide.swap.2.title':      'Burn MORM (passkey only)',
    'guide.swap.2.body':       'Burn is fully walletless: enter a µMORM amount and an EVM recipient (0x…), then your passkey signs a BRIDGE_BURN. The relayer observes the L1 burn and calls MORMBridge.unlock() on the EVM, releasing the locked ETH.',
    'guide.swap.3.title':      'Watch bridge status',
    'guide.swap.3.body':       'The status card shows the bridge contract address, its locked ETH balance, the cumulative lock/unlock nonce, and any L1 burns still waiting on relayer unlock. If the relayer is offline, pending burns will pile up here.',

    // ----- onboarding guide ---------------------------------------
    'guide.next':              'Next',
    'guide.prev':              'Back',
    'guide.skip':              'Skip',
    'guide.done':              'Got it',
    'guide.dont_show':         "Don't show again",
    'guide.help_btn':          '?',
    'guide.help_label':        'Show tutorial',
    'guide.step_of':           'Step {n} of {total}',

    // /upload steps
    'guide.upload.0.title':    'Welcome to MORM Creator',
    'guide.upload.0.body':     'MORM is a TikTok-style portrait video network. Every clip you upload is encoded into HLS, registered on chain, and earns the creator on-chain credit while viewers earn per-segment view rewards.',
    'guide.upload.1.title':    'Record a 9:16 clip',
    'guide.upload.1.body':     'Tap "Start camera" to grant access. Then "Record" to start, "Stop" to end. The recorder forces 9:16 portrait — landscape sources are auto-cropped on upload.',
    'guide.upload.2.title':    'Review and upload',
    'guide.upload.2.body':     'Your clip plays back as a preview. Hit "Upload & Encode" — the gateway re-encodes into 1080p/720p/480p/360p HLS ladders and registers the content on MORM Chain L1.',
    'guide.upload.3.title':    'Watch on the feed',
    'guide.upload.3.body':     'Once encoded (about a second per second of video), your clip appears at the bottom of the feed at /player-hls — anyone with a MORM identity can view + reward you.',

    // /player-hls steps
    'guide.player.0.title':    'Welcome to the feed',
    'guide.player.0.body':     'Swipe up (or scroll) to switch to the next clip. The browser snaps each card into view; only the active video is mounted, so memory and bandwidth stay flat no matter how many clips load.',
    'guide.player.1.title':    'Earn per-segment rewards',
    'guide.player.1.body':     'Each 3-second segment you watch fires a passkey-signed VIEW_REWARD tx that mints 1 µMORM directly to your wallet. Watch for the per-card HUD overlay tracking claims and balance.',
    'guide.player.2.title':    'Help share via P2P',
    'guide.player.2.body':     'When two viewers watch the same clip, the player tries to fetch segments directly from each other via WebRTC before falling back to the gateway. The HUD shows P2P hits + peer count + ICE mode.',

    // /wallet steps
    'guide.wallet.0.title':    'Welcome to your wallet',
    'guide.wallet.0.body':     'This page shows the policy that gates every MORM transaction your browser signs. Each page (shop, admin, upload, ...) gets its own allowed-kinds list and 24-hour spending cap.',
    'guide.wallet.1.title':    'Tighten or loosen per app',
    'guide.wallet.1.body':     'Tap the edit button on a row to change either the daily cap or the allowed transaction kinds. A hostile script on a page CANNOT silently broaden these — only this wallet UI can.',
    'guide.wallet.2.title':    '1-tap revocation',
    'guide.wallet.2.body':     'The big red button at the bottom wipes every per-app policy and resets the 24h spend counter. Use it after testing an untrusted page or if you suspect a compromised script.',
  },

  ja: {
    // ----- common -------------------------------------------------
    'common.cancel':           'キャンセル',
    'common.dismiss':          '閉じる',
    'common.refresh':          '↻ 再読込',
    'common.edit':             '編集',
    'common.save':             '保存',
    'common.signing_as':       '署名者: {addr}',
    'common.lang.en':          'EN',
    'common.lang.ja':          '日本語',
    'common.lang.label':       '言語',
    'common.identity_unset':   '— (/auth-morm でサインイン)',

    // ----- 27f tx confirm dialog ----------------------------------
    'confirm.title':           '🔐 トランザクションの確認',
    'confirm.button':          '確認して署名',
    'confirm.cancelled':       'ユーザーがキャンセルしました',

    // ----- 27g over-cap extra ceremony ----------------------------
    'cap.title':               '⚠ 24時間の送金上限を超過',
    'cap.app':                 'アプリ: {app}',
    'cap.kind':                'Tx種別: {kind}',
    'cap.this_amount':         '今回の送金額: {amount} MORM',
    'cap.spent24h':             '直近24時間の使用額: {spent} MORM',
    'cap.after':               '送金後の累計: {after} MORM',
    'cap.daily_cap':           '24時間上限: {cap} MORM',
    'cap.warn':                '不正なサイト、または改ざんされたページがウォレットを抜き取ろうとしている可能性があります。あなた自身が開始した送金のみ承認してください。',
    'cap.ack':                 '上限を超えることを理解した上で、それでも続行します。',
    'cap.approve':             '承認する',

    // ----- 27h kind blocked ---------------------------------------
    'block.title':             '🚫 このページではこのTx種別は許可されていません',
    'block.app':               'アプリ: {app}',
    'block.blocked_kind':      'ブロック: {kind}',
    'block.allowed':           'このアプリで許可中: {kinds}',
    'block.allowed_none':      '(なし)',
    'block.note':              'このTx種別はこのページの認可範囲外です。/wallet からポリシーを確認・拡張してください。',

    // ----- /wallet ------------------------------------------------
    'wallet.pill':             'ウォレット',
    'wallet.identity':         'アイデンティティ',
    'wallet.address':          'アドレス',
    'wallet.balance':          '残高',
    'wallet.nonce':            'ノンス',
    'wallet.policy_section':   'アプリ別ポリシー',
    'wallet.policy_hint':      '各 MORM ページには許可された Tx種別と 24時間あたりの送金上限が設定されています。ページ上の不正スクリプトがこれを勝手に拡張することはできません — SECURITY-DESIGN §3.4 (Phase 27g/h) 参照。各行を編集して制限を強めたり緩めたりできます。',
    'wallet.col.app':          'アプリ',
    'wallet.col.kinds':        '許可された種別',
    'wallet.col.cap':          '使用 / 上限 (24h)',
    'wallet.no_spend':         '送金不可',
    'wallet.fallback':         '既定',
    'wallet.editor.cap':       '24時間上限 (MORM、0 = 送金不可)',
    'wallet.editor.kinds':     '許可するトランザクション種別',
    'wallet.revoke_section':   '一括取り消し',
    'wallet.revoke_hint':      '全アプリ別ポリシーを破棄し、24時間の使用カウンタをリセットします。これ以降は、どのページからのTxも初回認可プロンプトを再表示します。スクリプト侵害の疑いがあるとき、または信用しないページでテストした後にお使いください。',
    'wallet.revoke_btn':       '🚨 一括取り消し (1タップ)',
    'wallet.revoke_confirm':   '全アプリのポリシーと24時間使用カウンタを破棄しますか?\n\n以降は各ページで再認可プロンプトが必要になります。',
    'wallet.revoke_done':      '✓ 取り消し完了 ({time})',
    'wallet.balance_unreach':  '— (RPC 未接続)',
    'wallet.no_identity':      '— (アイデンティティなし)',
    'wallet.loading':          '読み込み中…',

    // ----- /upload ------------------------------------------------
    'upload.pill':             '縦型アップロード',
    'upload.empty':             '「カメラ起動」をタップして開始',
    'upload.action.idle':      'カメラ起動',
    'upload.action.live':      '録画開始',
    'upload.action.recording': '停止',
    'upload.action.captured':  'アップロード & エンコード',
    'upload.action.uploading': 'アップロード中…',
    'upload.action.done':      'もう一度撮影',
    'upload.flip':             'カメラ切替',
    'upload.discard':          '撮影破棄',
    'upload.feed':             '▶ フィード',
    'upload.drop':             'またはファイルをドロップ / 選択',
    'upload.hud.job':          'ジョブ',
    'upload.hud.state':        '状態',
    'upload.hud.bytes':        'バイト',
    'upload.hud.elapsed':      '経過',
    'upload.hud.files':        '出力ファイル数',
    'upload.hud.content':      'コンテンツ',
    'upload.log.captured':     '撮影完了: {size} ({sec}秒, {mime})',
    'upload.log.uploaded':     'アップロード完了 ({sec}秒, job_id={id})',
    'upload.log.upload_fail':  'アップロード失敗: {err}',
    'upload.log.poll_fail':    'ポーリングエラー: {err}',
    'upload.log.done':         '✓ 完了 — フィードを開く',
    'upload.log.err':          '✗ エラー: {err}',
    'upload.cam_err':          'カメラエラー: {err}',
    'upload.unsupported':      'このブラウザは MediaRecorder に対応していません',
    'upload.feed_link':        '▶ 再生 {cid}…',

    // ----- /player-hls --------------------------------------------
    'player.pill':             '縦型フィード',
    'player.empty.loading':    '読み込み中…',
    'player.empty.none':       '(HLSコンテンツがありません — morm-core hls-encode を実行)',
    'player.empty.error':      'エラー: {err}',

    // ----- /swap (Phase 28a EVM ↔ MORM ブリッジ) -------------------
    'swap.pill':               'ブリッジ',
    'swap.tab.lock':           '⟶ ロック (ETH → MORM)',
    'swap.tab.burn':           '⟵ バーン (MORM → ETH)',
    'swap.lock.title':         'Ethereum 側で ETH をロック',
    'swap.lock.desc':          'EVM 上の MORMBridge.lock(bytes20) に Tx を送信します。マイニング完了後、Relayer が同額の µMORM を MORM Chain L1 のあなたの m0r… アドレスにミントします。',
    'swap.lock.connect':       'MetaMask に接続',
    'swap.lock.connected':     '接続済: {addr}',
    'swap.lock.no_metamask':   'MetaMask が見つかりません。インストールするか、下記の cast コマンドを手動実行してください。',
    'swap.lock.amount':        '送金額 (ETH)',
    'swap.lock.recipient':     'MORM 受取先 (m0r… または自分)',
    'swap.lock.use_mine':      '自分を使用',
    'swap.lock.btn':           'ETH をロック',
    'swap.lock.btn_busy':      '送信中…',
    'swap.lock.tx_sent':       'EVM Tx 送信: {hash}',
    'swap.lock.tx_mined':      '✓ EVM Tx ブロック {block} で確定',
    'swap.lock.tx_failed':     '✗ EVM Tx 失敗: {err}',
    'swap.lock.minted':        '✓ Relayer が {amount} µMORM を {addr} にミント (L1 残高更新)',
    'swap.lock.waiting_mint':  'Relayer が L1 にミントするのを待機中…',
    'swap.lock.fallback_hint': 'MetaMask がない場合、ターミナルで実行してください:',
    'swap.burn.title':         'MORM をバーンして ETH を解放',
    'swap.burn.desc':          'Passkey で BRIDGE_BURN Tx を署名します。Relayer が MORM Chain L1 上のバーンを観測し、EVM 上の MORMBridge.unlock() を呼び、ロック中の ETH を指定先に解放します。',
    'swap.burn.amount':        '送金額 (µMORM)',
    'swap.burn.recipient':     'EVM 受取先 (0x… 40 hex)',
    'swap.burn.btn':           'バーンしてアンロック要求',
    'swap.burn.btn_busy':      '署名中…',
    'swap.burn.signed':        '✓ MORM L1 バーン送信: {hash}',
    'swap.burn.unlocked':      '✓ Relayer が {amount} wei を {addr} にアンロック',
    'swap.burn.cancelled':     'ユーザーがバーンをキャンセル',
    'swap.burn.no_identity':   'MORM アイデンティティなし — 先に /auth-morm でサインイン',
    'swap.burn.failed':        '✗ バーン失敗: {err}',
    'swap.burn.waiting_unlock':'Relayer が EVM の unlock() を呼ぶのを待機中…',
    'swap.status.title':       'ブリッジ状態',
    'swap.status.contract':    'コントラクト',
    'swap.status.locked_eth':  'ロック中の ETH',
    'swap.status.lock_nonce':  'Lock nonce',
    'swap.status.unlock_nonce':'Unlock nonce',
    'swap.status.pending_burns':'処理待ちバーン (L1)',
    'swap.status.evm_chain':   'EVM チェーン',
    'swap.status.morm_rpc':    'MORM RPC',
    'swap.status.disabled':    'このゲートウェイではブリッジが未設定です。--bridge-addr <0x…> 付きで再起動してください。',

    // ----- /swap USDC tab (Phase 28b) -----------------------------
    'swap.tab.usdc':           'USDC',
    'swap.usdc.title':         'USDC ブリッジ (ERC-20)',
    'swap.usdc.desc':          'Ethereum 上の USDC (ERC-20) と MORM Chain L1 上の USDC.morm (1:1 ミラー残高) を相互変換します。Lock 側は ERC-20 仕様により事前に approve() が必要です。Burn 側は token=USDC を含む BRIDGE_BURN を passkey で署名します。',
    'swap.usdc.sub.lock':      '⟶ USDC をロック',
    'swap.usdc.sub.burn':      '⟵ USDC をバーン',
    'swap.usdc.your_balance':  '保有 USDC',
    'swap.usdc.allowance':     'ブリッジへの許可額',
    'swap.usdc.l1_balance':    '保有 USDC.morm',
    'swap.usdc.faucet':        '🪙 1000 USDC をミント (テスト)',
    'swap.usdc.faucet_done':   '✓ {addr} に 1000 USDC ミント完了',
    'swap.usdc.amount':        '送金額 (USDC)',
    'swap.usdc.approve_btn':   '1. ブリッジに USDC の引出許可を与える',
    'swap.usdc.approve_busy':  '承認中…',
    'swap.usdc.approve_done':  '✓ approve 完了: ブリッジが {amount} USDC を引き出せます',
    'swap.usdc.lock_btn':      '2. USDC をロック',
    'swap.usdc.lock_busy':     'ロック中…',
    'swap.usdc.locked':        '✓ Relayer が {amount} USDC.morm を {addr} にミント',
    'swap.usdc.burn_btn':      'USDC.morm をバーンして USDC を解放',
    'swap.usdc.burn_busy':     '署名中…',
    'swap.usdc.unlocked':      '✓ Relayer が {amount} USDC を {addr} に送付',
    'swap.usdc.need_approve':  '先に approve を実行してください — 現在 {allow} < 必要 {amount}',
    'swap.status.usdc_token':  'USDC トークン',
    'swap.status.usdc_bridge': 'USDC ブリッジ',
    'swap.status.usdc_locked': 'ロック中の USDC',

    // /swap onboarding steps
    'guide.swap.0.title':      'MORM ブリッジへようこそ',
    'guide.swap.0.body':       'このページは、Ethereum の ETH と MORM Chain L1 の µMORM を、フェデレーション式 lock/unlock ブリッジ (MORM.md §1, §4) で相互交換します。「ロック」側はミント、「バーン」側は解放です。',
    'guide.swap.1.title':      'ETH をロック (MetaMask 必要)',
    'guide.swap.1.body':       'MetaMask に接続し、ETH 額と MORM 受取先 (既定で自分の m0r…) を入力。送信すると MetaMask が MORMBridge.lock() に署名します。数秒以内に Relayer が L1 のあなたのアドレスに µMORM をミントします。',
    'guide.swap.2.title':      'MORM をバーン (Passkey のみ)',
    'guide.swap.2.body':       'バーン側は完全 walletless: µMORM 額と EVM 受取先 (0x…) を入力すれば passkey が BRIDGE_BURN を署名します。Relayer が L1 バーンを観測し EVM の unlock() を呼び、ロック中の ETH を解放します。',
    'guide.swap.3.title':      'ブリッジ状態を監視',
    'guide.swap.3.body':       '状態カードにはコントラクトアドレス、ロック中 ETH 残高、累積 lock/unlock nonce、Relayer 未処理の L1 バーンが表示されます。Relayer が停止していると、ここに溜まっていきます。',

    // ----- onboarding guide ---------------------------------------
    'guide.next':              '次へ',
    'guide.prev':              '戻る',
    'guide.skip':              'スキップ',
    'guide.done':              '了解',
    'guide.dont_show':         '次回から表示しない',
    'guide.help_btn':          '?',
    'guide.help_label':        '使い方を表示',
    'guide.step_of':           'ステップ {n} / {total}',

    // /upload steps
    'guide.upload.0.title':    'MORM クリエイターへようこそ',
    'guide.upload.0.body':     'MORM は TikTok 形式の縦型動画ネットワークです。アップロードされた各クリップは HLS にエンコードされチェーンに登録、クリエイターにはオンチェーンの実績が、視聴者には各セグメントごとに視聴報酬が支払われます。',
    'guide.upload.1.title':    '9:16 クリップを撮影',
    'guide.upload.1.body':     '「カメラ起動」をタップして権限を許可。「録画開始」で開始、「停止」で終了します。9:16 縦型に強制 — 横長ソースはアップロード時に自動的にクロップされます。',
    'guide.upload.2.title':    '確認してアップロード',
    'guide.upload.2.body':     'クリップがプレビュー再生されます。「アップロード & エンコード」をタップすると、ゲートウェイが 1080p/720p/480p/360p の HLS ladder に再エンコードし、MORM Chain L1 に登録します。',
    'guide.upload.3.title':    'フィードで視聴',
    'guide.upload.3.body':     'エンコード完了後 (動画 1 秒につき約 1 秒)、/player-hls フィードの末尾に表示されます。MORM アイデンティティを持つ誰もが視聴・報酬を送れます。',

    // /player-hls steps
    'guide.player.0.title':    'フィードへようこそ',
    'guide.player.0.body':     '上にスワイプ (またはスクロール) で次のクリップへ。ブラウザが各カードをスナップ表示し、アクティブな動画のみが mount されるため、何本クリップを読んでもメモリと帯域は一定です。',
    'guide.player.1.title':    'セグメントごとに報酬',
    'guide.player.1.body':     '視聴中の 3 秒セグメントごとに passkey 署名済の VIEW_REWARD tx が発行され、1 µMORM がウォレットに直接ミントされます。各カードの HUD で claim 数と残高をリアルタイム表示。',
    'guide.player.2.title':    'P2P で配信を分担',
    'guide.player.2.body':     '同じクリップを 2 人が視聴すると、player は WebRTC で互いから segment を直接取得してからゲートウェイにフォールバックします。HUD に P2P hits、peer 数、ICE モードを表示。',

    // /wallet steps
    'guide.wallet.0.title':    'ウォレットへようこそ',
    'guide.wallet.0.body':     'このページは、ブラウザが署名する全 MORM トランザクションを管理するポリシーを表示します。各ページ (shop / admin / upload / ...) ごとに「許可された Tx 種別」と「24時間の送金上限」が設定されています。',
    'guide.wallet.1.title':    'アプリ別に制限を変更',
    'guide.wallet.1.body':     '各行の編集ボタンをタップすると、24時間上限と許可 Tx 種別を変更できます。ページ上の不正スクリプトがこれを勝手に拡張することは不可能 — このウォレット UI からのみ可能です。',
    'guide.wallet.2.title':    '一括取り消し',
    'guide.wallet.2.body':     '画面下部の赤い大ボタンで全アプリ別ポリシーを破棄し、24時間使用カウンタもリセットします。信用しないページでテストした後や、スクリプト侵害の疑いがあるときに使用してください。',
  },
};

const STORAGE_KEY = 'morm-lang-v1';

function _detect() {
  const nav = (navigator.language || 'en').toLowerCase();
  return nav.startsWith('ja') ? 'ja' : 'en';
}

export function currentLang() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && DICT[stored]) return stored;
  } catch {}
  return _detect();
}

export function setLang(lang) {
  if (!DICT[lang]) lang = 'en';
  try { localStorage.setItem(STORAGE_KEY, lang); } catch {}
  document.documentElement.lang = lang;
  applyDom();
  // Notify any listening code (re-render dynamic content) via custom event.
  window.dispatchEvent(new CustomEvent('morm-lang-changed', { detail: { lang }}));
}

export function t(key, params = {}) {
  const lang = currentLang();
  const dict = DICT[lang] || DICT.en;
  let s = dict[key];
  if (s === undefined) s = DICT.en[key];
  if (s === undefined) s = key;   // missing key — show raw, easier to spot
  for (const [k, v] of Object.entries(params)) {
    s = s.replace(`{${k}}`, String(v));
  }
  return s;
}

/**
 * Walk `root` and rewrite every node tagged with a data-i18n attribute:
 *   data-i18n="key"             → element.textContent = t(key)
 *   data-i18n-html="key"        → element.innerHTML  = t(key) (CAUTION:
 *     we only allow this for known-safe keys with embedded HTML in the
 *     dictionary. Keys never contain user input.)
 *   data-i18n-placeholder="key" → element.placeholder = t(key)
 *   data-i18n-title="key"       → element.title = t(key)
 *   data-i18n-aria-label="key"  → element.setAttribute('aria-label', t(key))
 */
export function applyDom(root = document) {
  for (const el of root.querySelectorAll('[data-i18n]')) {
    el.textContent = t(el.dataset.i18n);
  }
  for (const el of root.querySelectorAll('[data-i18n-html]')) {
    el.innerHTML = t(el.dataset.i18nHtml);
  }
  for (const el of root.querySelectorAll('[data-i18n-placeholder]')) {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  }
  for (const el of root.querySelectorAll('[data-i18n-title]')) {
    el.title = t(el.dataset.i18nTitle);
  }
  for (const el of root.querySelectorAll('[data-i18n-aria-label]')) {
    el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
  }
}

/**
 * Insert a small EN | 日本語 toggle into `parent`. Calls `setLang` and
 * re-renders. Highlights the active language. Pages that mount this
 * once on load get persistent toggling for free.
 */
export function mountLangToggle(parent, opts = {}) {
  const wrap = document.createElement('span');
  wrap.style.cssText =
    'display:inline-flex; gap:4px; align-items:center; ' +
    'font-size:11px; pointer-events:auto; ' +
    (opts.style || '');
  wrap.setAttribute('aria-label', t('common.lang.label'));
  const make = (lang, label) => {
    const a = document.createElement('a');
    a.href = '#';
    a.textContent = label;
    a.dataset.lang = lang;
    a.style.cssText =
      'padding:2px 6px; border-radius:6px; text-decoration:none; ' +
      'border:1px solid #3a4150; color:#6a7a90; cursor:pointer;';
    a.onclick = (e) => { e.preventDefault(); setLang(lang); paint(); };
    return a;
  };
  const en = make('en', t('common.lang.en'));
  const ja = make('ja', t('common.lang.ja'));
  wrap.appendChild(en); wrap.appendChild(ja);
  function paint() {
    const cur = currentLang();
    for (const a of [en, ja]) {
      const active = a.dataset.lang === cur;
      a.style.color       = active ? '#0a1218'  : '#6a7a90';
      a.style.background  = active ? '#4dd2ff'  : 'transparent';
      a.style.borderColor = active ? '#4dd2ff'  : '#3a4150';
      a.style.fontWeight  = active ? '700'      : '400';
    }
  }
  paint();
  parent.appendChild(wrap);
  return wrap;
}

// Auto-apply on DOM ready so pages that just include `data-i18n` tags
// don't need to call applyDom() themselves.
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => applyDom());
  } else {
    applyDom();
  }
  document.documentElement.lang = currentLang();
}
