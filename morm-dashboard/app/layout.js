import "./globals.css";

export const metadata = {
  title: "MORM Node Dashboard - PCクラスタ管理",
  description: "PC Cluster Management Dashboard with MORM (m0r) Token Rewards",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ja">
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta property="og:image" content="/icons/og-image.png" />
      </head>
      <body>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
