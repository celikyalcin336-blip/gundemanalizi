<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0" 
    xmlns:html="http://www.w3.org/TR/REC-html40"
    xmlns:sitemap="http://www.sitemaps.org/schemas/sitemap/0.9"
    xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"
    xmlns:video="http://www.google.com/schemas/sitemap-video/1.1"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" version="1.0" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <html xmlns="http://www.w3.org/1999/xhtml" lang="tr">
      <head>
        <title>Gündem Analizi - XML Site Haritası</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style type="text/css">
          * { box-sizing: border-box; margin: 0; padding: 0; }
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #0b0f19;
            color: #cbd5e1;
            padding: 30px 20px;
            line-height: 1.5;
          }
          .container {
            max-width: 1100px;
            margin: 0 auto;
          }
          .header {
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
          }
          .brand {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
          }
          .badge {
            background: #dc2626;
            color: #fff;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
          h1 {
            color: #ffffff;
            font-size: 24px;
            font-weight: 900;
            letter-spacing: -0.5px;
          }
          p.desc {
            color: #94a3b8;
            font-size: 13px;
            margin-top: 6px;
          }
          .back-link {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #dc2626;
            color: #ffffff;
            text-decoration: none;
            font-size: 12px;
            font-weight: 700;
            padding: 8px 16px;
            border-radius: 8px;
            margin-top: 14px;
            transition: background 0.2s;
          }
          .back-link:hover {
            background: #b91c1c;
          }
          .stats-bar {
            display: flex;
            gap: 16px;
            margin-bottom: 20px;
          }
          .stat-box {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 14px 20px;
            flex: 1;
          }
          .stat-num {
            color: #f8fafc;
            font-size: 20px;
            font-weight: 800;
          }
          .stat-label {
            color: #64748b;
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 600;
          }
          table {
            width: 100%;
            border-collapse: collapse;
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
          }
          th {
            background: #1e293b;
            color: #e2e8f0;
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 14px 16px;
            text-align: left;
            border-bottom: 1px solid #334155;
          }
          td {
            padding: 12px 16px;
            font-size: 12px;
            border-bottom: 1px solid #1e293b;
            color: #94a3b8;
          }
          tr:hover td {
            background: #1e293b/40;
            color: #e2e8f0;
          }
          td a {
            color: #38bdf8;
            text-decoration: none;
            font-weight: 600;
            word-break: break-all;
          }
          td a:hover {
            color: #7dd3fc;
            text-decoration: underline;
          }
          .title-col {
            color: #f1f5f9;
            font-weight: 700;
          }
          .tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            background: #1e293b;
            color: #cbd5e1;
          }
          .footer {
            text-align: center;
            margin-top: 30px;
            color: #475569;
            font-size: 11px;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <div class="brand">
              <span class="badge">XML Site Haritası</span>
              <span style="color:#64748b; font-size:12px;">| Google &amp; Arama Motoru İndeksleyici</span>
            </div>
            <h1>Gündem Analizi - Canlı Site Haritası</h1>
            <p class="desc">
              Bu XML site haritası, Google News, Yandex ve Bing botlarının en son haberlerimizi anında tarayabilmesi için dinamik olarak üretilmektedir.
            </p>
            <a href="/" class="back-link">← Gündem Analizi Anasayfasına Dön</a>
          </div>

          <div class="stats-bar">
            <div class="stat-box">
              <div class="stat-num"><xsl:value-of select="count(sitemap:urlset/sitemap:url)"/></div>
              <div class="stat-label">Toplam İndeksli Bağlantı</div>
            </div>
            <div class="stat-box">
              <div class="stat-num">CANLI</div>
              <div class="stat-label">Google News &amp; SEO Durumu</div>
            </div>
            <div class="stat-box">
              <div class="stat-num">UTF-8 / XML</div>
              <div class="stat-label">Protokol Uyumluluğu</div>
            </div>
          </div>

          <table>
            <thead>
              <tr>
                <th style="width: 50px;">#</th>
                <th>Sayfa / Haber Başlığı &amp; Bağlantısı</th>
                <th style="width: 140px;">Yayın Tarihi</th>
                <th style="width: 90px; text-align: center;">Öncelik</th>
              </tr>
            </thead>
            <tbody>
              <xsl:for-each select="sitemap:urlset/sitemap:url">
                <tr>
                  <td><xsl:value-of select="position()"/></td>
                  <td>
                    <!-- If News title exists -->
                    <xsl:if test="news:news/news:title">
                      <div class="title-col"><xsl:value-of select="news:news/news:title"/></div>
                    </xsl:if>
                    <!-- If Video title exists -->
                    <xsl:if test="video:video/video:title">
                      <div class="title-col"><xsl:value-of select="video:video/video:title"/></div>
                    </xsl:if>
                    <a href="{sitemap:loc}" target="_blank">
                      <xsl:value-of select="sitemap:loc"/>
                    </a>
                  </td>
                  <td>
                    <xsl:choose>
                      <xsl:when test="news:news/news:publication_date">
                        <xsl:value-of select="substring(news:news/news:publication_date, 1, 16)"/>
                      </xsl:when>
                      <xsl:when test="sitemap:lastmod">
                        <xsl:value-of select="sitemap:lastmod"/>
                      </xsl:when>
                      <xsl:otherwise>
                        <span class="tag">Otomatik</span>
                      </xsl:otherwise>
                    </xsl:choose>
                  </td>
                  <td style="text-align: center;">
                    <xsl:choose>
                      <xsl:when test="sitemap:priority">
                        <span class="tag"><xsl:value-of select="sitemap:priority"/></span>
                      </xsl:when>
                      <xsl:otherwise>
                        <span class="tag">0.8</span>
                      </xsl:otherwise>
                    </xsl:choose>
                  </td>
                </tr>
              </xsl:for-each>
            </tbody>
          </table>

          <div class="footer">
            © 2026 Gündem Analizi - Doğru Haber, Tarafsız Analiz. Tüm Hakları Saklıdır.
          </div>
        </div>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
