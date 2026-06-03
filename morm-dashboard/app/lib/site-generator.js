import fs from 'fs';
import path from 'path';

/**
 * Read DESIGN.md and extract design tokens (colors, fonts) from the first 100 lines.
 */
function readDesignTokens(designSource, designTemplate) {
  try {
    const designPath = path.join(process.cwd(), 'public', `design-md-${designSource}`, designTemplate, 'DESIGN.md');
    const content = fs.readFileSync(designPath, 'utf-8');
    const lines = content.split('\n').slice(0, 100);
    const text = lines.join('\n');

    // Extract colors
    const colorMatches = text.match(/#[0-9a-fA-F]{3,8}/g) || [];
    const colors = [...new Set(colorMatches)];

    // Extract font families
    const fontMatch = text.match(/font[- ]?family[:\s]*[`"']?([^`"'\n,]+)/i);
    const fontName = fontMatch ? fontMatch[1].trim() : null;

    // Determine primary/accent colors
    const primaryColor = colors.find(c => c.length >= 6 && c !== '#fff' && c !== '#ffffff' && c !== '#000' && c !== '#000000') || '#667eea';
    const accentColor = colors.find(c => c !== primaryColor && c.length >= 6 && c !== '#fff' && c !== '#ffffff' && c !== '#000' && c !== '#000000') || '#764ba2';
    const bgDark = colors.find(c => c === '#000' || c === '#000000' || c === '#111' || c === '#1d1d1f') || '#0c0c1d';
    const bgLight = colors.find(c => c === '#fff' || c === '#ffffff' || c === '#f5f5f7' || c === '#fafafa') || '#f5f5f7';
    const textColor = colors.find(c => c === '#1d1d1f' || c === '#333' || c === '#111') || '#e0e0e0';

    return {
      primaryColor,
      accentColor,
      bgDark,
      bgLight,
      textColor,
      fontFamily: fontName || 'system-ui, -apple-system, sans-serif',
      templateName: designTemplate,
    };
  } catch (e) {
    // Fallback defaults
    return {
      primaryColor: '#667eea',
      accentColor: '#764ba2',
      bgDark: '#0c0c1d',
      bgLight: '#f5f5f7',
      textColor: '#e0e0e0',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      templateName: designTemplate || 'default',
    };
  }
}

function slugify(text) {
  return text.toLowerCase().replace(/[^a-z0-9\u3000-\u9fff]+/g, '-').replace(/^-|-$/g, '');
}

/**
 * Generate a complete blog site HTML.
 */
export function generateBlogSite(config) {
  const { title, theme, keywords, designTemplate, designSource } = config;
  const tokens = readDesignTokens(designSource || 'jp', designTemplate || 'apple');
  const keywordList = (keywords || theme || 'technology').split(/[\s,、]+/).filter(Boolean);
  const mainKeyword = keywordList[0] || 'technology';

  const articles = [];
  const articleTitles = [
    `${theme}の最新トレンド：2026年に注目すべきポイント`,
    `初心者向け${theme}入門ガイド`,
    `${theme}が変える未来のビジネス`,
    `${theme}活用事例：成功企業に学ぶ`,
    `${theme}の基礎知識と実践テクニック`,
  ];

  for (let i = 0; i < 5; i++) {
    const articleTitle = articleTitles[i];
    const slug = `article-${i + 1}`;
    const content = `<p>${theme}に関する最新の動向をお伝えします。${keywordList.join('、')}といったキーワードが注目を集めています。この分野では技術革新が続いており、多くの企業が積極的に投資を進めています。</p><p>特に${mainKeyword}の分野では、新しいアプローチが次々と登場しています。専門家の間では、今後さらなる発展が期待されており、関連する技術やサービスの需要は拡大し続けるでしょう。</p>`;
    articles.push({ title: articleTitle, content, slug, sortOrder: i });
  }

  const articleCardsHtml = articles.map((a, i) => `
    <article class="article-card">
      <img src="https://picsum.photos/seed/${mainKeyword}${i}/800/600" alt="${a.title}" loading="lazy" />
      <div class="article-body">
        <h3>${a.title}</h3>
        ${a.content}
        <a href="#" class="read-more">続きを読む →</a>
      </div>
    </article>
  `).join('\n');

  const html = `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${title}</title>
  <meta name="description" content="${theme}に関する情報を発信するブログサイト" />
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: ${tokens.fontFamily};
      background: ${tokens.bgDark};
      color: ${tokens.textColor};
      line-height: 1.7;
    }
    a { color: ${tokens.primaryColor}; text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* Nav */
    .site-nav {
      background: rgba(12, 12, 29, 0.92);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding: 1rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .site-nav .logo {
      font-size: 1.3rem;
      font-weight: 700;
      background: linear-gradient(135deg, ${tokens.primaryColor}, ${tokens.accentColor});
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .site-nav .nav-links { display: flex; gap: 1.5rem; }
    .site-nav .nav-links a { color: rgba(255,255,255,0.7); font-size: 0.9rem; }
    .site-nav .nav-links a:hover { color: #fff; }

    /* Hero */
    .hero {
      text-align: center;
      padding: 6rem 2rem;
      background: linear-gradient(180deg, rgba(12,12,29,0.8) 0%, ${tokens.bgDark} 100%),
                  linear-gradient(135deg, ${tokens.primaryColor}22, ${tokens.accentColor}22);
    }
    .hero h1 {
      font-size: clamp(2rem, 5vw, 3.5rem);
      font-weight: 800;
      margin-bottom: 1rem;
      background: linear-gradient(135deg, ${tokens.primaryColor}, ${tokens.accentColor});
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .hero p {
      font-size: 1.15rem;
      color: rgba(255,255,255,0.6);
      max-width: 600px;
      margin: 0 auto;
    }

    /* Articles */
    .articles {
      max-width: 1200px;
      margin: 0 auto;
      padding: 4rem 2rem;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 2rem;
    }
    .article-card {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      overflow: hidden;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .article-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 40px rgba(0,0,0,0.4);
    }
    .article-card img {
      width: 100%;
      height: 200px;
      object-fit: cover;
    }
    .article-body {
      padding: 1.5rem;
    }
    .article-body h3 {
      font-size: 1.15rem;
      font-weight: 700;
      margin-bottom: 0.8rem;
      color: #fff;
    }
    .article-body p {
      font-size: 0.9rem;
      color: rgba(255,255,255,0.6);
      margin-bottom: 0.6rem;
    }
    .read-more {
      display: inline-block;
      margin-top: 0.5rem;
      font-size: 0.85rem;
      font-weight: 600;
      color: ${tokens.primaryColor};
    }

    /* Ad slot */
    .ad-slot {
      max-width: 728px;
      margin: 2rem auto;
      min-height: 90px;
      background: rgba(255,255,255,0.02);
      border: 1px dashed rgba(255,255,255,0.1);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: rgba(255,255,255,0.2);
      font-size: 0.8rem;
    }

    /* Footer */
    .site-footer {
      text-align: center;
      padding: 3rem 2rem;
      border-top: 1px solid rgba(255,255,255,0.06);
      color: rgba(255,255,255,0.3);
      font-size: 0.85rem;
    }

    @media (max-width: 640px) {
      .articles { grid-template-columns: 1fr; padding: 2rem 1rem; }
      .hero { padding: 4rem 1.5rem; }
    }
  </style>
</head>
<body>
  <nav class="site-nav">
    <span class="logo">${title}</span>
    <div class="nav-links">
      <a href="#">ホーム</a>
      <a href="#">記事一覧</a>
      <a href="#">お問い合わせ</a>
    </div>
  </nav>

  <section class="hero">
    <h1>${theme}の最新情報</h1>
    <p>${theme}に関する最新ニュース、トレンド、実践的なガイドをお届けします。</p>
  </section>

  <div class="ad-slot">AD SPACE</div>

  <section class="articles">
    ${articleCardsHtml}
  </section>

  <div class="ad-slot">AD SPACE</div>

  <footer class="site-footer">
    <p>&copy; 2026 ${title}. All rights reserved.</p>
    <p style="margin-top: 0.5rem;">Design inspired by ${tokens.templateName}</p>
  </footer>
</body>
</html>`;

  const pages = articles.map((a, i) => ({
    title: a.title,
    content: a.content,
    slug: a.slug,
  }));

  return { html, pages };
}

/**
 * Generate a landing page HTML.
 */
export function generateLPSite(config) {
  const { title, theme, keywords, designTemplate, designSource } = config;
  const tokens = readDesignTokens(designSource || 'jp', designTemplate || 'apple');
  const keywordList = (keywords || theme || 'technology').split(/[\s,、]+/).filter(Boolean);
  const mainKeyword = keywordList[0] || 'technology';

  const html = `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${title}</title>
  <meta name="description" content="${title} - ${theme}のランディングページ" />
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: ${tokens.fontFamily};
      background: ${tokens.bgDark};
      color: ${tokens.textColor};
      line-height: 1.7;
    }
    a { color: ${tokens.primaryColor}; text-decoration: none; }

    /* Nav */
    .site-nav {
      background: rgba(12, 12, 29, 0.92);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding: 1rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .site-nav .logo {
      font-size: 1.3rem;
      font-weight: 700;
      background: linear-gradient(135deg, ${tokens.primaryColor}, ${tokens.accentColor});
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .btn-primary {
      display: inline-block;
      padding: 0.8rem 2rem;
      background: linear-gradient(135deg, ${tokens.primaryColor}, ${tokens.accentColor});
      color: #fff;
      border-radius: 50px;
      font-weight: 600;
      font-size: 1rem;
      border: none;
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .btn-primary:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 30px ${tokens.primaryColor}44;
      text-decoration: none;
    }

    /* Hero */
    .hero-lp {
      text-align: center;
      padding: 8rem 2rem 6rem;
      background: linear-gradient(180deg, ${tokens.bgDark} 0%, rgba(12,12,29,0.6) 100%),
                  radial-gradient(ellipse at 50% 0%, ${tokens.primaryColor}15, transparent 70%);
    }
    .hero-lp h1 {
      font-size: clamp(2.2rem, 5vw, 4rem);
      font-weight: 800;
      margin-bottom: 1.2rem;
      background: linear-gradient(135deg, #fff, rgba(255,255,255,0.8));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .hero-lp p {
      font-size: 1.2rem;
      color: rgba(255,255,255,0.5);
      max-width: 600px;
      margin: 0 auto 2.5rem;
    }

    /* Features */
    .section { padding: 5rem 2rem; max-width: 1100px; margin: 0 auto; }
    .section-title {
      text-align: center;
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 3rem;
      color: #fff;
    }
    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 2rem;
    }
    .feature-card {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      padding: 2rem;
      text-align: center;
      transition: transform 0.2s;
    }
    .feature-card:hover { transform: translateY(-4px); }
    .feature-icon {
      font-size: 2.5rem;
      margin-bottom: 1rem;
    }
    .feature-card h3 {
      font-size: 1.15rem;
      color: #fff;
      margin-bottom: 0.8rem;
    }
    .feature-card p {
      font-size: 0.9rem;
      color: rgba(255,255,255,0.5);
    }

    /* Stats */
    .stats-section {
      background: rgba(255,255,255,0.02);
      border-top: 1px solid rgba(255,255,255,0.06);
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 2rem;
      text-align: center;
    }
    .stat-number {
      font-size: 3rem;
      font-weight: 800;
      background: linear-gradient(135deg, ${tokens.primaryColor}, ${tokens.accentColor});
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .stat-label {
      font-size: 0.9rem;
      color: rgba(255,255,255,0.5);
      margin-top: 0.3rem;
    }

    /* Testimonials */
    .testimonials-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 2rem;
    }
    .testimonial-card {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      padding: 2rem;
    }
    .testimonial-card p {
      font-size: 0.95rem;
      color: rgba(255,255,255,0.6);
      font-style: italic;
      margin-bottom: 1rem;
    }
    .testimonial-author {
      font-weight: 600;
      color: ${tokens.primaryColor};
      font-size: 0.9rem;
    }

    /* CTA */
    .cta-section {
      text-align: center;
      padding: 6rem 2rem;
      background: radial-gradient(ellipse at 50% 50%, ${tokens.primaryColor}10, transparent 70%);
    }
    .cta-section h2 {
      font-size: 2rem;
      color: #fff;
      margin-bottom: 1rem;
    }
    .cta-section p {
      color: rgba(255,255,255,0.5);
      margin-bottom: 2rem;
      max-width: 500px;
      margin-left: auto;
      margin-right: auto;
    }

    /* Ad slot */
    .ad-slot {
      max-width: 728px;
      margin: 2rem auto;
      min-height: 90px;
      background: rgba(255,255,255,0.02);
      border: 1px dashed rgba(255,255,255,0.1);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: rgba(255,255,255,0.2);
      font-size: 0.8rem;
    }

    /* Footer */
    .site-footer {
      text-align: center;
      padding: 3rem 2rem;
      border-top: 1px solid rgba(255,255,255,0.06);
      color: rgba(255,255,255,0.3);
      font-size: 0.85rem;
    }

    @media (max-width: 640px) {
      .hero-lp { padding: 5rem 1.5rem 4rem; }
      .stats-grid { grid-template-columns: 1fr; }
      .section { padding: 3rem 1rem; }
    }
  </style>
</head>
<body>
  <nav class="site-nav">
    <span class="logo">${title}</span>
    <a href="#cta" class="btn-primary" style="padding: 0.5rem 1.5rem; font-size: 0.85rem;">今すぐ始める</a>
  </nav>

  <section class="hero-lp">
    <h1>${title}</h1>
    <p>${theme}で、あなたのビジネスを次のレベルへ。革新的なソリューションをご提供します。</p>
    <a href="#cta" class="btn-primary">無料で試す</a>
  </section>

  <section class="section">
    <h2 class="section-title">特徴</h2>
    <div class="features-grid">
      <div class="feature-card">
        <div class="feature-icon">⚡</div>
        <h3>高速パフォーマンス</h3>
        <p>${theme}の最新技術を活用し、圧倒的な処理速度を実現。ストレスフリーな体験をお届けします。</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">🔒</div>
        <h3>セキュリティ</h3>
        <p>最先端の暗号化技術とセキュリティ対策で、大切なデータを完全に保護します。</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">🚀</div>
        <h3>スケーラビリティ</h3>
        <p>ビジネスの成長に合わせて柔軟にスケール。${mainKeyword}の力で無限の可能性を。</p>
      </div>
    </div>
  </section>

  <section class="section stats-section">
    <div class="stats-grid">
      <div>
        <div class="stat-number">10,000+</div>
        <div class="stat-label">アクティブユーザー</div>
      </div>
      <div>
        <div class="stat-number">99.9%</div>
        <div class="stat-label">稼働率</div>
      </div>
      <div>
        <div class="stat-number">500+</div>
        <div class="stat-label">導入企業</div>
      </div>
    </div>
  </section>

  <div class="ad-slot">AD SPACE</div>

  <section class="section">
    <h2 class="section-title">お客様の声</h2>
    <div class="testimonials-grid">
      <div class="testimonial-card">
        <p>「${theme}の導入により、業務効率が大幅に改善しました。チーム全体の生産性が向上しています。」</p>
        <div class="testimonial-author">田中太郎 - CEO, テックコープ</div>
      </div>
      <div class="testimonial-card">
        <p>「使いやすさと高機能を両立した素晴らしいサービスです。サポートも迅速で信頼できます。」</p>
        <div class="testimonial-author">佐藤花子 - CTO, イノベーションラボ</div>
      </div>
      <div class="testimonial-card">
        <p>「コスト削減と品質向上を同時に実現できました。${mainKeyword}の未来を感じるプロダクトです。」</p>
        <div class="testimonial-author">鈴木一郎 - PM, デジタルソリューションズ</div>
      </div>
    </div>
  </section>

  <section class="cta-section" id="cta">
    <h2>今すぐ始めましょう</h2>
    <p>${theme}の力で、ビジネスを変革する準備はできていますか？</p>
    <a href="#" class="btn-primary">無料トライアルを開始</a>
  </section>

  <div class="ad-slot">AD SPACE</div>

  <footer class="site-footer">
    <p>&copy; 2026 ${title}. All rights reserved.</p>
    <p style="margin-top: 0.5rem;">Design inspired by ${tokens.templateName}</p>
  </footer>
</body>
</html>`;

  const pages = [
    { title: `${title} - トップ`, content: html, slug: 'index' },
  ];

  return { html, pages };
}

/**
 * Inject ad codes into generated HTML based on ad settings from DB.
 * @param {string} html - The generated HTML string
 * @param {Array} adSettings - Array of ad_settings rows from DB
 * @returns {string} Modified HTML with ads injected
 */
export function injectAds(html, adSettings) {
  if (!adSettings || adSettings.length === 0) return html;

  const enabledAds = adSettings.filter(a => a.enabled);
  if (enabledAds.length === 0) return html;

  let result = html;

  for (const ad of enabledAds) {
    const hasCode = ad.ad_code && ad.ad_code.trim().length > 0;

    switch (ad.ad_type) {
      case 'popunder': {
        const snippet = hasCode
          ? `\n<!-- Adsterra Popunder -->\n${ad.ad_code}\n`
          : `\n<!-- Ad Placeholder: popunder -->\n<script>/* Adsterra Popunder code will be placed here */</script>\n`;
        result = result.replace('</body>', snippet + '</body>');
        break;
      }
      case 'social_bar': {
        const snippet = hasCode
          ? `\n<!-- Adsterra Social Bar -->\n${ad.ad_code}\n`
          : `\n<!-- Ad Placeholder: social_bar -->\n<script>/* Adsterra Social Bar code will be placed here */</script>\n`;
        result = result.replace('</body>', snippet + '</body>');
        break;
      }
      case 'banner_728': {
        const bannerHtml = hasCode
          ? `\n<!-- Adsterra Banner 728x90 -->\n<div class="ad-slot ad-banner-728" style="text-align:center;padding:10px;margin:16px auto;max-width:728px;">\n${ad.ad_code}\n</div>\n`
          : `\n<!-- Ad Placeholder: banner_728 -->\n<div class="ad-slot ad-banner-728" style="text-align:center;padding:10px;background:rgba(0,0,0,0.03);border-radius:8px;margin:16px auto;max-width:728px;">\n  <div style="color:#999;font-size:12px;">広告スペース (728x90)</div>\n  <!-- Adsterra code here -->\n</div>\n`;
        // After </nav>
        result = result.replace('</nav>', '</nav>' + bannerHtml);
        // Before </footer> (only first footer)
        result = result.replace(/<footer/i, bannerHtml + '<footer');
        break;
      }
      case 'banner_300': {
        const bannerHtml = hasCode
          ? `\n<!-- Adsterra Banner 300x250 -->\n<div class="ad-slot ad-banner-300" style="text-align:center;padding:10px;margin:16px auto;max-width:300px;">\n${ad.ad_code}\n</div>\n`
          : `\n<!-- Ad Placeholder: banner_300 -->\n<div class="ad-slot ad-banner-300" style="text-align:center;padding:10px;background:rgba(0,0,0,0.03);border-radius:8px;margin:16px auto;max-width:300px;">\n  <div style="color:#999;font-size:12px;">広告スペース (300x250)</div>\n  <!-- Adsterra code here -->\n</div>\n`;
        // Insert before articles section or in article sidebar area
        result = result.replace(/<section class="articles">/i, bannerHtml + '<section class="articles">');
        break;
      }
      case 'native': {
        const nativeHtml = hasCode
          ? `\n<!-- Adsterra Native Banner -->\n<div class="ad-slot ad-native" style="padding:10px;margin:16px auto;max-width:728px;">\n${ad.ad_code}\n</div>\n`
          : `\n<!-- Ad Placeholder: native -->\n<div class="ad-slot ad-native" style="text-align:center;padding:10px;background:rgba(0,0,0,0.03);border-radius:8px;margin:16px auto;max-width:728px;">\n  <div style="color:#999;font-size:12px;">ネイティブ広告</div>\n  <!-- Adsterra code here -->\n</div>\n`;
        // Insert between article cards (after 2nd article)
        const articleCardRegex = /(<\/article>\s*)/;
        let count = 0;
        result = result.replace(/(<\/article>\s*)/g, (match) => {
          count++;
          if (count === 2) return match + nativeHtml;
          return match;
        });
        break;
      }
      case 'direct_link': {
        // Direct links are handled differently - just add a comment marker
        if (hasCode) {
          const snippet = `\n<!-- Adsterra Direct Link -->\n${ad.ad_code}\n`;
          result = result.replace('</body>', snippet + '</body>');
        }
        break;
      }
    }
  }

  return result;
}
